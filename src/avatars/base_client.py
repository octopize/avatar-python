from __future__ import annotations

import itertools
import os
import time
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

from avatars.constants import FileLike, FileLikes
from avatars.utils import (
    ContentType,
    ensure_valid,
    is_text_file_or_buffer,
    pop_or,
    remove_optionals,
    validated,
)

logger = structlog.getLogger(__name__)
structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())

DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_RETRY_INTERVAL = 5
DEFAULT_RETRY_COUNT = 20
DEFAULT_TIMEOUT = 60 * 4
DEFAULT_PER_CALL_TIMEOUT = 15

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


class ClientTimeout:
    def __init__(self, *, timeout: float, max_seconds: float = 10):
        self.retry_seconds: float = timeout
        self.max_seconds: float = max_seconds
        self.is_active: bool = False
        self.last_time: float = 0
        self.elapsed_seconds: float = 0
        self.interval: Optional[Iterator[float]] = None

    def start(self) -> None:
        self.is_active = True
        self.last_time = time.time()
        self.elapsed_seconds = 0

        # Exponential interval, capped at max_interval
        self.sleep_interval = iter(min(2**i, self.max_seconds) for i in itertools.count())

    def stop(self) -> None:
        self.is_active = False

    def update(self) -> None:
        now = time.time()
        self.elapsed_seconds += now - self.last_time
        self.last_time = now

    def is_expired(self) -> bool:
        return self.elapsed_seconds > self.retry_seconds

    def next_interval(self) -> float:
        interval = next(self.sleep_interval)

        if self.elapsed_seconds > self.retry_seconds:
            interval = min(interval, self.retry_seconds - self.elapsed_seconds)

        return float(interval)

    def intervals(self, label: str) -> Iterator[float]:
        self.start()

        # Iterate while we are < retry_timeout
        while not self.is_expired() and self.is_active:
            yield self.next_interval()
            self.update()

        if self.is_active and self.is_expired():
            raise TimeoutError(f"{label} expired")


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
    json_data: Optional[BaseModel] = None
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

    def build_json_data_arg(self) -> Optional[str]:
        return json_loads(self.json_data.model_dump_json()) if self.json_data else None

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
        self.timeout: Optional[ClientTimeout] = None
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
        retry_count: int = DEFAULT_RETRY_COUNT + 1,  # stop is inclusive
        retry_inverval: int = DEFAULT_RETRY_INTERVAL,
    ) -> Iterator[tenacity.AttemptManager]:
        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(retry_count),
            wait=tenacity.wait_exponential(max=retry_inverval),
            before_sleep=_log_before_retry_attempt,
            retry_error_callback=lambda call_state: _reraise_on_timeout(
                call_state, data=self.data
            ),
            after=lambda call_state: _log_after_failure(call_state, data=self.data),
            reraise=True,
        ):
            yield attempt

    def send_request(self) -> Response:
        first_or_retry_all = True

        while first_or_retry_all:
            first_or_retry_all = False
            request = ensure_valid(self.data.http_request)

            for attempt in self.retry(DEFAULT_RETRY_COUNT + 1, DEFAULT_RETRY_INTERVAL):
                with attempt:
                    self.data.http_response = self.http_client.send(
                        request=request,
                        stream=self.data.should_stream,
                    )

                    if self.check_auth_refreshed():
                        # Reset/rebuild current request
                        first_or_retry_all = True
                        self.build_request()
                        break

        self.check_success()

        return ensure_valid(self.data.http_response)

    def send_request_and_build_response(self, response_cls: type[ResponseClass]) -> ResponseClass:
        self.send_request()

        return self.build_response(response_cls)

    def build_and_send_request(self) -> Any:
        self.build_request()

        return self.send_request()

    def build_response(self, response_cls: type[ResponseClass]) -> ResponseClass:
        return response_cls(**self.data.response_to_json())

    def cancel_timeout(self) -> None:
        if self.timeout:
            self.timeout.stop()

    def wait_intervals(self, label: str) -> Iterator[float]:
        self.timeout = ClientTimeout(timeout=DEFAULT_RETRY_TIMEOUT)
        self.timeout.start()

        for interval in self.timeout.intervals(label):
            yield interval

        self.timeout = None

    def loop_until(
        self,
        *,
        label: str,
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

            logger.info(f"waiting {what_label}(loop {loops}, sleeping {DEFAULT_RETRY_INTERVAL}s)")
            time.sleep(DEFAULT_RETRY_INTERVAL)

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

    def raise_on_status(self, resp: Response) -> None:
        content = self.data.get_user_content() or "no message available"

        if isinstance(content, dict):
            self.check_authenticated(resp, content)

            standard_error = _get_nested_value(content, "message")

            if standard_error:
                error_msg = standard_error
            elif validation_error := _get_nested_value(content, "msg"):
                if detailed_message := _get_nested_value(content, "loc"):
                    field = detailed_message[-1]
                    error_msg = f"{validation_error}: {field}"
                else:
                    error_msg = f"Bad Request: {validation_error}"
            else:
                error_msg = "Internal error: " + str(content)
        else:
            error_msg = content

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
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        should_verify_ssl: bool = True,
        *,
        verify_auth: bool = True,
        on_auth_refresh: Optional[AuthRefreshFunc] = None,
        http_client: Optional[httpx.Client] = None,
        headers: Dict[str, str] = {},
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
        timeout: Optional[int] = None,
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
                label=f"created resource is ready at {url}",
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
