from __future__ import annotations

import itertools
import logging
import os
import time
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
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
    Type,
    TypeVar,
    Union,
    cast,
)

import httpx
from httpx import ReadTimeout, Request, Response, WriteTimeout
from pydantic import BaseModel

from avatars.arrow_utils import (
    ArrowStreamReader,
    ArrowStreamWriter,
    FileLike,
    FileLikes,
    is_text_file_or_buffer,
)
from avatars.models import JobStatus
from avatars.utils import ContentType, ensure_valid, pop_or, remove_optionals, validated

logger = logging.getLogger(__name__)

DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_RETRY_INTERVAL = 5
DEFAULT_RETRY_COUNT = 20
DEFAULT_TIMEOUT = 60 * 4
DEFAULT_PER_CALL_TIMEOUT = 15

IN_PROGRESS_STATUSES = (JobStatus.pending, JobStatus.started)

DEFAULT_BINARY_CONTENT_TYPES = (
    ContentType.PDF,
    ContentType.OCTET_STREAM,
    ContentType.ARROW_STREAM,
)
DEFAULT_TEXT_CONTENT_TYPES = (ContentType.CSV, ContentType.JSON)

T = TypeVar("T")
R = TypeVar("R")
RequestClass = TypeVar("RequestClass", bound=BaseModel)
ResponseClass = TypeVar("ResponseClass", bound=BaseModel)

JsonLike = dict[str, Any]

Content = Union[Iterable[bytes], bytes]
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


class Timeout(Exception):
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
        self.sleep_interval = iter(
            min(2**i, self.max_seconds) for i in itertools.count()
        )

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
            raise Timeout(f"{label} expired")


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
    files: Optional[FileLikes] = None
    content: Optional[Content] = None
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

    def build_form_data_arg(self) -> Optional[Dict[str, Any]]:
        arg = (
            self.form_data.model_dump()
            if isinstance(self.form_data, BaseModel)
            else self.form_data
        )

        return remove_optionals(arg)

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
        return self.ensure_status_is(httpx.codes.CREATED) and self.has_header(
            "location"
        )

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
                with ArrowStreamReader() as reader:
                    reader.write_parquet(destination, resp.iter_bytes())
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

    def stream_response(
        self, destination: Optional[FileLike] = None
    ) -> StreamedContent:
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

        if isinstance(destination, str):
            destination_data = open(destination, "wb")
        else:
            destination_data = destination or buffer

        self.stream_response_content(destination_data)

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
            files=self.data.files,  # type: ignore[arg-type]
            content=self.data.content,
            headers=self.data.headers,
            timeout=DEFAULT_PER_CALL_TIMEOUT,
        )

        return ensure_valid(self.data.http_request)

    def send_request(self) -> Response:
        refreshed = False
        request = ensure_valid(self.data.http_request)

        error_to_raise_after_retry: Optional[Exception] = None
        nb_retries_left = DEFAULT_RETRY_COUNT

        while True:
            try:
                self.data.http_response = self.http_client.send(
                    request=request,
                    stream=self.data.should_stream,
                )

                # Reset retry parameters
                error_to_raise_after_retry = None

                if self.check_auth_refreshed():
                    if refreshed:
                        # Don't loop forever trying to refresh auth
                        logger.warning("Authentication was already refreshed once")
                        break
                    else:
                        refreshed = True
                        continue  # Retry current request with new auth
                else:
                    break  # Success, does not run finally
            except httpx.ConnectError as e:
                if "EOF occurred in violation of protocol" in str(e):
                    msg = f"Got EOF error on {self.data.url}."
                    logger.warning(msg)
                    error_to_raise_after_retry = e
                else:
                    raise e
            except (ReadTimeout, WriteTimeout):
                msg = (
                    f"Timeout waiting for {self.data.method.upper()} on {self.data.url}"
                )
                logger.info(msg)
                error_to_raise_after_retry = Timeout(msg)

            if error_to_raise_after_retry:
                if nb_retries_left > 0:
                    nb_retries_left -= 1
                    logger.info(f"Retrying in {DEFAULT_RETRY_INTERVAL}s...")
                    time.sleep(DEFAULT_RETRY_INTERVAL)
                else:
                    raise error_to_raise_after_retry

        self.check_success()

        return ensure_valid(self.data.http_response)

    def send_request_and_build_response(
        self, response_cls: type[ResponseClass]
    ) -> ResponseClass:
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

            logger.info(
                f"waiting {what_label}"
                f"(loop {loops}, sleeping {DEFAULT_RETRY_INTERVAL}s)"
            )
            time.sleep(DEFAULT_RETRY_INTERVAL)

            loops += 1

        if not response_cls:
            info.response = self.data.get_user_content()

        return info

    def check_success(self) -> None:
        resp = ensure_valid(self.data.http_response, "response")

        if resp.is_success:
            return

        if self.data.should_stream:
            content = resp.read()
            encoding = resp.encoding or "utf-8"
            as_json: Dict[str, Any] = json_loads(content.decode(encoding))
            self.raise_on_status(resp, as_json)
        else:
            self.raise_on_status(resp, resp.json())

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

    def raise_on_status(self, resp: Response, content: dict[str, Any]) -> None:
        if not content:
            content = resp.json()

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
            error_msg = "Internal error"

        raise Exception(
            f"Got error in HTTP request: {self.data.method} {self.data.url}."
            f" Error status {resp.status_code} - {error_msg}"
        )


def update_request_op(info: OperationInfo) -> bool:
    info.in_progress = info.data.status_is(httpx.codes.ACCEPTED)
    return False


def update_response_op(info: OperationInfo, response: ResponseClass) -> bool:
    ret: bool = False

    if hasattr(response, "status"):
        info.in_progress = response.status in IN_PROGRESS_STATUSES
    else:
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
            raise ValueError(
                f"Expected base_url not to contain quotes. Got {base_url} instead"
            )

        self.base_url = base_url
        self.timeout = timeout
        self.should_verify_ssl = should_verify_ssl
        self.verify_auth = verify_auth
        self._on_auth_refresh = on_auth_refresh or (lambda: {})
        self._http_client = http_client
        self._headers = {"Avatars-Accept-Created": "yes"} | headers

    def set_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    def on_auth_refresh(
        self, on_auth_refresh: Optional[AuthRefreshFunc] = None
    ) -> None:
        self._on_auth_refresh = on_auth_refresh or (lambda: {})

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
                if isinstance(f, str) and Path(f).is_file():
                    prepared_files.append(stack.enter_context(open(f, "rb")))
                else:
                    raise ValueError(
                        f"Expected streamable file-like object, got {f} instead"
                    )

        return prepared_files

    def prepare_content(
        self, stack: ExitStack, headers: dict[str, Any], keyword_args: dict[str, Any]
    ) -> Optional[Content]:
        content: Optional[Content] = None

        if "dataset" in keyword_args:
            content = ArrowStreamWriter(keyword_args.pop("dataset"))
            headers["Content-Type"] = ContentType.ARROW_STREAM.value

        return content

    @contextmanager
    def context(
        self, *, ctx: Optional[ClientContext] = None, **kwargs: Any
    ) -> Generator[ClientContext, None, None]:
        with ExitStack() as stack:
            http_client = self._http_client or httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                verify=self.should_verify_ssl,
            )

            # Grab special keys
            headers: dict[str, Any] = pop_or(kwargs, "headers", {})
            files = self.prepare_files(stack, headers, kwargs)
            content = self.prepare_content(stack, headers, kwargs)
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
            ctx.data.content = content
            ctx.data.want_content = want_content

            yield ctx

            ctx.data.files = None
            ctx.data.content = None
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

    def wait_created(
        self, *, ctx: ClientContext, url: str, **kwargs: Any
    ) -> OperationInfo:
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

    def get_job(
        self,
        *,
        url: str,
        response_cls: Type[ResponseClass],
        **kwargs: Any,
    ) -> ResponseClass:
        with self.context(method="get", url=url) as ctx:
            ctx.build_and_send_request()

            info = ctx.loop_until(
                label=f"get job at {url}",
                update_func=update_response_op,
                response_cls=response_cls,
            )

            return cast(ResponseClass, info.response)

    def __str__(self) -> str:
        return ", ".join(
            f"ApiClient(base_url={self.base_url}"
            f"timeout={self.timeout}"
            f"should_verify_ssl={self.should_verify_ssl}"
            f"verify_auth={self.verify_auth})"
        )
