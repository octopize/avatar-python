from __future__ import annotations

import os
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO, IOBase
from json import loads as json_loads
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import httpx
import structlog
import tenacity
from httpx import Request, Response
from pydantic import BaseModel

from avatars.constants import (
    DEFAULT_NETWORK_RETRY_COUNT,
    DEFAULT_NETWORK_RETRY_INTERVAL,
    DEFAULT_RATE_LIMIT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT_MIN_WAIT_SECONDS,
    FileLike,
    FileLikes,
)
from avatars.utils import (
    ContentType,
    ensure_valid,
    is_text_file_or_buffer,
    pop_or,
    remove_optionals,
    validated,
)

logger = structlog.getLogger(__name__)

DEFAULT_TIMEOUT = 60 * 4

DEFAULT_BINARY_CONTENT_TYPES = (
    ContentType.PDF,
    ContentType.OCTET_STREAM,
)
DEFAULT_TEXT_CONTENT_TYPES = (ContentType.CSV, ContentType.JSON)

T = TypeVar("T")
R = TypeVar("R")
RequestClass = TypeVar("RequestClass", bound=BaseModel)
ResponseClass = TypeVar("ResponseClass", bound=BaseModel)

JsonLike = dict[str, Any]

Content = Union[Iterable[bytes], bytes]
ContentBuilderFunc = Optional[Callable[..., Content]]
UserContent = Union[JsonLike, str, bytes, Optional[BytesIO]]
StreamedContent = Optional[Union[BytesIO, bytes, str]]

AuthRefreshFunc = Optional[Callable[..., dict[str, str]]]


def _get_nested_value(
    obj: Union[Mapping[Any, Any], Sequence[Any]], key: str, default: Any = None
) -> Any:
    """
    Return value from (possibly) nested key in JSON dictionary.
    """
    if isinstance(obj, Sequence) and not isinstance(obj, str):
        for item in obj:
            return _get_nested_value(item, key, default=default)

    if isinstance(obj, Mapping):
        if key in obj:
            return obj[key]
        return _get_nested_value(list(obj.values()), key, default=default)

    return default


def _log_before_retry_attempt(retry_state: tenacity.RetryCallState) -> None:
    if not retry_state.next_action:
        logger.info(" log_before_retry_attempt no next action")
        return
    next_retry_seconds = retry_state.next_action.sleep
    logger.info(f"Retrying in {next_retry_seconds}s...")


def _log_rate_limit_retry(retry_state: tenacity.RetryCallState) -> None:
    """Log rate limit retry attempts with relevant details."""
    if retry_state.outcome and retry_state.outcome.failed:
        e = retry_state.outcome.exception()
        if isinstance(e, RateLimitError):
            retry_after = e.retry_after
            sleep_duration = max(DEFAULT_RATE_LIMIT_MIN_WAIT_SECONDS, retry_after)
            logger.debug(
                "rate limit exceeded, retrying after delay",
                retry_after=retry_after,
                sleep_duration=sleep_duration,
                retry_attempt=retry_state.attempt_number,
                max_retries=DEFAULT_RATE_LIMIT_MAX_RETRIES,
            )


def _log_after_failure(retry_state: tenacity.RetryCallState, *, data: ContextData) -> None:
    if not retry_state.outcome:
        return

    if retry_state.outcome.failed:
        e = retry_state.outcome.exception()
        error_message = str(e)
        logger.warning(error_message, url=data.url, base_url=data.base_url)


def _reraise_on_timeout(retry_state: tenacity.RetryCallState, *, data: ContextData) -> None:
    """After last retry attempt, if the outcome is a timeout, raise a custom exception."""
    if not retry_state.outcome:
        return

    if retry_state.outcome.failed:
        e = retry_state.outcome.exception()
        if isinstance(e, (httpx.ReadTimeout, httpx.WriteTimeout)):
            msg = f"Timeout waiting for {data.method.upper()} on {data.url}"
            raise TimeoutError(msg)
        raise e  # type: ignore[misc] # Exception must be derived from BaseException


class TimeoutError(Exception):
    pass


class RateLimitError(Exception):
    """Raised when a request is rate limited (HTTP 429)."""

    def __init__(self, message: str, retry_after: int, response: Response) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.response = response


@dataclass
class ContextData:
    base_url: str
    method: str
    url: str
    headers: dict[str, str]
    http_request: Optional[Request] = None
    http_response: Optional[Response] = None
    timeout: float = 0.0
    params: Optional[Dict[str, Any]] = None
    json_data: Optional[Union[BaseModel, Dict[str, Any], list[Any]]] = None
    form_data: Optional[Union[BaseModel, Dict[str, Any]]] = None
    data: Optional[str] = None
    files: Optional[FileLikes] = None
    content_builder: ContentBuilderFunc = None
    should_verify_auth: bool = True
    should_stream: bool = False
    destination: Optional[FileLike] = None
    want_content: bool = False

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def build_params_arg(self) -> Optional[Dict[str, Any]]:
        return remove_optionals(self.params)

    def build_json_data_arg(self) -> Optional[Union[Dict[str, Any], list[Any]]]:
        if not self.json_data:
            return None

        if isinstance(self.json_data, BaseModel):
            return json_loads(self.json_data.model_dump_json())
        else:
            # Handle plain lists, dicts, etc.
            return self.json_data

    def build_form_data_arg(self) -> Mapping[str, Any] | None:
        arg = (
            self.form_data.model_dump()
            if isinstance(self.form_data, BaseModel)
            else self.form_data
        )

        return remove_optionals(arg)

    def build_files_arg(self) -> Optional[list[Tuple[str, Any]]]:
        return [("file", file) for file in self.files] if self.files else None

    def build_content_arg(self) -> Optional[Content]:
        return self.content_builder() if self.content_builder else None

    def status_is(self, status_code: int) -> bool:
        if self.http_response:
            return self.http_response.status_code == status_code

        return False

    def ensure_status_is(self, status_code: int) -> bool:
        if self.http_response:
            if not self.status_is(status_code):
                raise Exception(
                    f"Expected code {status_code}"
                    f" for {self.method} on {self.url}"
                    f", got {self.http_response.status_code} instead"
                )

            return True
        else:
            raise Exception("Expected a HTTP response, got None instead")

    def has_header(self, header: str) -> bool:
        if self.http_response and header in self.http_response.headers:
            return True

        return False

    def get_header(self, header: str) -> Any:
        return ensure_valid(self.http_response).headers[header]

    def update_headers(self, headers: dict[str, str]) -> None:
        self.headers |= headers

        if self.http_request:
            self.http_request.headers.update(headers)

    def content_type(self) -> ContentType:
        return ContentType(self.get_header("content-type").split(";")[0].strip())

    def is_created(self) -> bool:
        return self.status_is(httpx.codes.CREATED) and self.has_header("location")

    def ensure_created(self) -> bool:
        return self.ensure_status_is(httpx.codes.CREATED) and self.has_header("location")

    def is_content_json(self) -> bool:
        return bool(self.content_type() == ContentType.JSON)

    def is_content_arrow(self) -> bool:
        return bool(self.content_type() == ContentType.ARROW_STREAM)

    def is_content_text(self) -> bool:
        return self.content_type() in DEFAULT_TEXT_CONTENT_TYPES

    def is_content_binary(self) -> bool:
        return self.content_type() in DEFAULT_BINARY_CONTENT_TYPES

    def get_user_content(self) -> UserContent:
        with validated(self.http_response, "response") as resp:
            if self.should_stream:
                return self.stream_response()
            else:
                if self.is_content_json():
                    return self.response_to_json()
                elif self.is_content_binary():
                    return resp.content
                else:
                    return resp.text

    def get_content_message(self) -> str:
        content = self.get_user_content()
        msg = ""

        if isinstance(content, dict):
            if "detail" in content:
                if "message" in content["detail"]:
                    msg = content["detail"]["message"]
        elif isinstance(content, str):
            msg = content
        else:
            logger.warning(f"Expected readable content, got {type(content)} instead")

        return msg

    def response_to_json(self) -> dict[str, Any]:
        resp = ensure_valid(self.http_response, "response")

        as_json: Dict[str, Any] = {}

        if self.is_content_json():
            as_json = resp.json()

        return as_json

    def stream_response_content(self, destination: FileLike) -> None:
        with validated(self.http_response, "response") as resp:
            if self.is_content_arrow():
                # with ArrowStreamReader() as reader:
                #     reader.write_parquet(destination, resp.iter_bytes())
                pass
            else:
                try:
                    if is_text_file_or_buffer(destination):
                        for chunk in resp.iter_text():
                            destination.write(chunk)  # type: ignore[call-overload]
                    else:
                        # Assume bytes...
                        for chunk in resp.iter_bytes():  # type: ignore[assignment]
                            destination.write(chunk)  # type: ignore[call-overload]
                finally:
                    resp.close()

    def stream_response(self, destination: Optional[FileLike] = None) -> StreamedContent:
        """
        Handle the streaming of a response to a destination.

        If the destination is not provided, it returns the content as bytes.

        This needs the httpx.Client instance to remain open, even though no client
        is used in this function.

        Parameters
        ----------
        response
            The response object to be streamed.
        destination
            The destination where the response will be streamed.
            If not provided, the content is returned as.

        Returns
        -------
            If no destination was provided, it returns the raw bytes.
        """
        content: StreamedContent = None
        buffer = BytesIO()
        opened = False

        if isinstance(destination, str):
            opened = True
            destination_data = open(destination, "wb")
        else:
            destination_data = destination or buffer

        self.stream_response_content(destination_data)

        if isinstance(destination_data, IOBase):
            logger.info(f"base_client: flushing {destination=}")
            destination_data.flush()

        if opened:
            logger.info(f"base_client: closing {destination=}")
            destination_data.close()

        buffer.seek(0, os.SEEK_SET)

        content = buffer if not destination else None

        if self.want_content and content:
            content = content.read()

            if self.is_content_text():
                content = content.decode()

        return content

    def clone(self) -> ContextData:
        return deepcopy(self)


@dataclass
class OperationInfo:
    data: ContextData
    in_progress: bool = False
    last_updated_at: datetime = field(default_factory=datetime.now)
    response: Optional[Any] = None


class ClientContext:
    def __init__(
        self,
        http_client: httpx.Client,
        data: ContextData,
        on_auth_refresh: AuthRefreshFunc = None,
    ) -> None:
        self.http_client: httpx.Client = http_client
        self.data: ContextData = data
        self.on_auth_refresh = on_auth_refresh

    def build_request(self) -> Request:
        self.data.http_request = self.http_client.build_request(
            method=self.data.method,
            url=self.data.url,
            params=self.data.build_params_arg(),
            json=self.data.build_json_data_arg(),
            data=self.data.build_form_data_arg(),
            files=self.data.build_files_arg(),
            content=self.data.build_content_arg(),
            headers=self.data.headers,
            timeout=None,
        )

        return ensure_valid(self.data.http_request)

    def retry(
        self,
        retry_count: int,  # Note: stop is inclusive
        retry_interval: Optional[int],
    ) -> Iterator[tenacity.AttemptManager]:
        """
        Unified retry mechanism for both network and rate limit errors.

        Parameters
        ----------
        retry_count
            Maximum number of retry attempts
        retry_interval
            If provided, uses exponential backoff with this max interval.
            If None, uses rate limit retry strategy with retry_after from server.
        """

        if retry_interval is None:
            # Rate limit mode: custom wait based on server's retry_after
            def wait_for_rate_limit(retry_state: tenacity.RetryCallState) -> float:
                """Custom wait strategy that respects retry_after for rate limits."""
                if retry_state.outcome and retry_state.outcome.failed:
                    e = retry_state.outcome.exception()
                    if isinstance(e, RateLimitError):
                        return max(DEFAULT_RATE_LIMIT_MIN_WAIT_SECONDS, e.retry_after)
                return 0

            wait_strategy = wait_for_rate_limit
            before_sleep_func = _log_rate_limit_retry
            retry_condition = tenacity.retry_if_exception_type(RateLimitError)
            # Don't log after failure for rate limits - only specific rate limit log
            after_func = None
            retry_error_callback_func = None
        else:
            # Network retry mode: exponential backoff
            wait_strategy = tenacity.wait_exponential(max=retry_interval)
            before_sleep_func = _log_before_retry_attempt
            retry_condition = tenacity.retry_if_exception_type(Exception)

            def after_func(call_state):
                _log_after_failure(call_state, data=self.data)

            def retry_error_callback_func(call_state):
                _reraise_on_timeout(call_state, data=self.data)

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(retry_count),
            wait=wait_strategy,
            retry=retry_condition,
            before_sleep=before_sleep_func,
            retry_error_callback=retry_error_callback_func,
            after=after_func,
            reraise=True,
        ):
            yield attempt

    def send_request(self) -> None:
        needs_retry_with_auth = True

        while needs_retry_with_auth:
            needs_retry_with_auth = False
            # Capture the request once per auth retry - reuse for all retries
            request = ensure_valid(self.data.http_request)

            # Application-level retries (rate limits)
            for rate_limit_attempt in self.retry(
                DEFAULT_RATE_LIMIT_MAX_RETRIES + 1, retry_interval=None
            ):
                with rate_limit_attempt:
                    # Network-level retries (timeouts, connection errors, ...)
                    for attempt in self.retry(
                        DEFAULT_NETWORK_RETRY_COUNT + 1, DEFAULT_NETWORK_RETRY_INTERVAL
                    ):
                        with attempt:
                            self.data.http_response = self.http_client.send(
                                request=request,
                                stream=self.data.should_stream,
                            )

                            if self.check_auth_refreshed():
                                # Reset/rebuild current request
                                needs_retry_with_auth = True
                                self.build_request()
                                break

                    if needs_retry_with_auth:
                        break

                    # Check for rate limiting (will raise RateLimitError if 429)
                    # Tenacity will catch this and retry with the same request
                    self.check_success()

    def send_request_and_build_response(self, response_cls: type[ResponseClass]) -> ResponseClass:
        self.send_request()

        return self.build_response(response_cls)

    def build_and_send_request(self) -> None:
        self.build_request()

        self.send_request()

    def build_response(self, response_cls: type[ResponseClass]) -> ResponseClass:
        return response_cls(**self.data.response_to_json())

    def loop_until(
        self,
        *,
        update_func: Callable[..., bool],
        response_cls: Optional[Type[ResponseClass]] = None,
    ) -> OperationInfo:
        def call_update_func(info: OperationInfo) -> bool:
            if response_cls:
                info.response = self.build_response(response_cls)
                return update_func(info, info.response)
            else:
                return update_func(info)

        info = OperationInfo(data=self.data)
        what = str(response_cls) if response_cls else "request"
        what_label = f"for {what} at {self.data.url} to complete"
        loops = 1

        self.build_request()
        info.in_progress = True

        while info.in_progress:
            self.send_request()

            stop = call_update_func(info)

            if stop or not info.in_progress:
                break

            logger.info(
                f"waiting {what_label}(loop {loops}, sleeping {DEFAULT_NETWORK_RETRY_INTERVAL}s)"
            )

            loops += 1

        if not response_cls:
            info.response = self.data.get_user_content()

        return info

    def check_success(self) -> None:
        resp = ensure_valid(self.data.http_response, "response")

        if resp.is_success:
            return

        self.raise_on_status(resp)

    def check_auth_refreshed(
        self,
    ) -> bool:
        refreshed = False

        if self.data.status_is(httpx.codes.UNAUTHORIZED):
            msg = self.data.get_content_message()

            if "credentials expired" in msg:
                if self.on_auth_refresh:
                    logger.info("trying to refresh authentication token")
                    new_headers = self.on_auth_refresh()
                    self.data.update_headers(new_headers)
                    logger.info("authentication refreshed, retrying previous request")
                    refreshed = True
                else:
                    logger.warning("Authentication refresh needed but not configured")

        return refreshed

    def check_authenticated(self, resp: Response, content: dict[str, Any]) -> None:
        value = content.get("detail")

        if (
            resp.status_code == httpx.codes.UNAUTHORIZED
            and isinstance(value, str)
            and "authenticated" in value
        ):
            raise Exception("You are not authenticated.")

    def _check_rate_limit(self, resp: Response, content: UserContent, error_msg: str) -> None:
        if resp.status_code == 429:
            retry_after = 0
            if isinstance(content, dict):
                retry_after = content.get("retry_after", 0)

            # Also check the Retry-After header as fallback
            if "retry-after" in resp.headers:
                try:
                    retry_after = int(resp.headers["retry-after"])
                except (ValueError, TypeError):
                    pass

            logger.debug(
                "rate limit response received",
                url=self.data.url,
                method=self.data.method,
                retry_after=retry_after,
                detail=error_msg,
            )

            raise RateLimitError(
                f"Rate limit exceeded for {self.data.method} {self.data.url}: {error_msg}",
                retry_after=retry_after,
                response=resp,
            )

    def _extract_error_message(self, content: UserContent) -> str:
        """Extract error message from response content."""
        if not isinstance(content, dict):
            return str(content)

        # Try standard error field
        if standard_error := _get_nested_value(content, "message"):
            return standard_error

        # Try validation error
        if validation_error := _get_nested_value(content, "msg"):
            if detailed_message := _get_nested_value(content, "loc"):
                field = detailed_message[-1]
                return f"{validation_error}: {field}"
            return f"Bad Request: {validation_error}"

        # Default to detail or full content
        if detail := content.get("detail"):
            return str(detail)

        return f"Internal error: {content}"

    def raise_on_status(self, resp: Response) -> None:
        content = self.data.get_user_content()
        error_msg = self._extract_error_message(content or "no message available")

        # Raise RateLimitError if applicable
        self._check_rate_limit(resp, content, error_msg)

        if isinstance(content, dict):
            # Raise "Not authenticated" error if applicable
            self.check_authenticated(resp, content)

        raise Exception(
            f"Got error in HTTP request: {self.data.method} {self.data.url}."
            f" Error status {resp.status_code} - {error_msg}"
        )


def update_request_op(info: OperationInfo) -> bool:
    info.in_progress = info.data.status_is(httpx.codes.ACCEPTED)
    return False


def update_response_op(info: OperationInfo, response: ResponseClass) -> bool:
    ret: bool = False

    # if hasattr(response, "status"):
    #     info.in_progress = response.status in IN_PROGRESS_STATUSES
    # else:
    # ret = update_request_op(info)
    ret = update_request_op(info)

    if hasattr(response, "last_updated_at"):
        info.last_updated_at = response.last_updated_at

    return ret


class BaseClient:
    def __init__(
        self,
        base_url: str,
        timeout: int = DEFAULT_TIMEOUT,
        should_verify_ssl: bool = True,
        *,
        verify_auth: bool = True,
        on_auth_refresh: Optional[AuthRefreshFunc] = None,
        http_client: Optional[httpx.Client] = None,
        headers: Dict[str, str] = {},
        api_key: Optional[str] = None,
    ) -> None:
        """Client to communicate with the Avatar API.

        Parameters
        ----------
        base_url
            url of the API
        timeout:
            timeout in seconds, by default DEFAULT_TIMEOUT
        should_verify_ssl :, optional
            whether to verify SSL certificates on the server. By default True
        http_client :, optional
            allow passing in custom httpx.Client instance, by default None
        verify_auth :, optional
            Bypass client-side authentication verification, by default True
        api_key :, optional
            API key for authentication. If provided, uses api-key-v1 scheme
            instead of Bearer tokens. By default None
        """
        if '"' in base_url:
            raise ValueError(f"Expected base_url not to contain quotes. Got {base_url} instead")

        self.base_url = base_url
        self.timeout = timeout
        self.should_verify_ssl = should_verify_ssl
        self.verify_auth = verify_auth
        self._on_auth_refresh = on_auth_refresh
        self._http_client = http_client
        self._headers = {"Avatars-Accept-Created": "yes"} | headers
        self._api_key: Optional[str] = api_key

        # Set API key auth header if provided
        if self._api_key:
            self.set_header("Authorization", f"api-key-v1 {self._api_key}")
            # Disable auth refresh for API keys since they don't expire
            self._on_auth_refresh = None

    def set_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    def on_auth_refresh(self, on_auth_refresh: Optional[AuthRefreshFunc] = None) -> None:
        self._on_auth_refresh = on_auth_refresh

    def prepare_files(
        self, stack: ExitStack, headers: dict[str, Any], keyword_args: dict[str, Any]
    ) -> Optional[FileLikes]:
        files: Any = pop_or(keyword_args, "files", [])
        files = files if isinstance(files, list) else [files]

        if f := pop_or(keyword_args, "file", None):
            files.append(f)

        prepared_files: Optional[FileLikes] = None

        if files:
            prepared_files = []

            for f in files:
                if isinstance(f, (str, Path)) and Path(f).is_file():
                    prepared_files.append(stack.enter_context(open(f, "rb")))
                else:
                    raise ValueError(f"Expected streamable file-like object, got {f} instead")

        return prepared_files

    def make_content_builder(self, keyword_args: dict[str, Any]) -> ContentBuilderFunc:
        content_builder: ContentBuilderFunc = None

        if "content" in keyword_args:
            content = keyword_args.pop("content")
            content_builder = lambda: content  # noqa
        # elif "dataset" in keyword_args:
        #     ds = keyword_args.pop("dataset")
        #     headers["Content-Type"] = ContentType.ARROW_STREAM.value
        #     content_builder = lambda: ArrowStreamWriter(ds)  # noqa

        return content_builder

    @contextmanager
    def context(
        self, *, ctx: Optional[ClientContext] = None, **kwargs: Any
    ) -> Generator[ClientContext, None, None]:
        with ExitStack() as stack:
            if not self._http_client:
                http_client = stack.enter_context(
                    httpx.Client(
                        base_url=self.base_url,
                        timeout=self.timeout,
                        verify=self.should_verify_ssl,
                    )
                )
            else:
                # Will be closed by the caller
                http_client = self._http_client

            # Grab special keys
            headers: dict[str, Any] = pop_or(kwargs, "headers", {})
            files = self.prepare_files(stack, headers, kwargs)
            content_builder = self.make_content_builder(kwargs)
            want_content: bool = pop_or(kwargs, "want_content", False)

            if not ctx:
                ctx = ClientContext(
                    http_client=http_client,
                    data=ContextData(
                        base_url=self.base_url, headers=self._headers.copy(), **kwargs
                    ),
                    on_auth_refresh=self._on_auth_refresh,
                )

            ctx.data.update(**kwargs)
            ctx.data.headers.update(headers)
            ctx.data.files = files
            ctx.data.content_builder = content_builder
            ctx.data.want_content = want_content

            yield ctx

            ctx.data.files = None
            ctx.data.content_builder = None
            ctx.data.want_content = False

    def create(
        self,
        *,
        url: str,
        request: RequestClass,
        response_cls: Type[ResponseClass],
    ) -> ResponseClass:
        with self.context(method="post", url=url) as ctx:
            ctx.data.json_data = request
            ctx.build_and_send_request()
            ctx.data.ensure_created()

            info = self.wait_created(
                url=ctx.data.get_header("location"),
                update_func=update_response_op,
                response_cls=response_cls,
                ctx=ctx,
            )

            return cast(ResponseClass, info.response)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        response: Any = None

        with self.context(method=method, url=url, **kwargs) as ctx:
            ctx.build_and_send_request()
            destination = kwargs.get("destination", None)

            if destination:
                response = ctx.data.stream_response(destination=destination)
            elif ctx.data.is_created():
                response = self.wait_created(
                    url=ctx.data.get_header("location"),
                    update_func=update_request_op,
                    ctx=ctx,
                ).response
            else:
                response = ctx.data.get_user_content()

        return response

    def wait_created(self, *, ctx: ClientContext, url: str, **kwargs: Any) -> OperationInfo:
        with self.context(method="get", url=url, ctx=ctx) as ctx:
            return ctx.loop_until(
                **kwargs,
            )

    def check_auth(self, data: ContextData) -> None:
        should_verify = self.verify_auth and data.should_verify_auth

        if should_verify and "Authorization" not in self._headers:
            raise Exception("You are not authenticated.")

    def send_request(self, *, method: str, url: str, **kwargs: Any) -> Any:
        """Request the API."""
        with self.context(method=method, url=url, **kwargs) as ctx:
            self.check_auth(ctx.data)
            ctx.build_and_send_request()

            return ctx.data.get_user_content()
