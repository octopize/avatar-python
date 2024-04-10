from __future__ import annotations

import itertools
import logging
import time
from datetime import datetime
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from io import BytesIO
from json import loads as json_loads
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
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

from avatars.models import JobStatus
from avatars.utils import (
    callable_type_match,
    ensure_valid,
    pop_or,
    validated,
    remove_optionals,
)


if TYPE_CHECKING:
    from avatars._typing import FileLikeInterface, HttpxFile

logger = logging.getLogger(__name__)

DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_RETRY_INTERVAL = 5
DEFAULT_RETRY_COUNT = 4
DEFAULT_TIMEOUT = 60 * 4
DEFAULT_PER_CALL_TIMEOUT = 15

IN_PROGRESS_STATUSES = (JobStatus.pending, JobStatus.started)

DEFAULT_BINARY_CONTENT_TYPES = ("application/pdf", "application/octet-stream")

T = TypeVar("T")
R = TypeVar("R")
RequestClass = TypeVar("RequestClass", bound=BaseModel)
ResponseClass = TypeVar("ResponseClass", bound=BaseModel)


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
    file: Optional[Sequence["HttpxFile"]] = None
    should_verify_auth: bool = True
    should_stream: bool = False

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

    def is_created(self) -> bool:
        return self.status_is(httpx.codes.CREATED) and self.has_header("location")

    def ensure_created(self) -> None:
        self.ensure_status_is(httpx.codes.CREATED) and self.has_header("location")

    def is_content_json(self) -> bool:
        return bool(self.get_header("content-type") == "application/json")

    def is_content_binary(self) -> bool:
        return self.get_header("content-type") in DEFAULT_BINARY_CONTENT_TYPES

    def get_user_content(self) -> Any:
        with validated(self.http_response, "response") as resp:
            if self.should_stream:
                return self.stream_response(resp)
            else:
                if self.is_content_json():
                    return self.response_to_json()
                elif self.is_content_binary():
                    return resp.content
                else:
                    return resp.text

    def response_to_json(self) -> dict[str, Any]:
        resp = ensure_valid(self.http_response, "response")

        as_json: Dict[str, Any] = {}

        if self.is_content_json():
            as_json = resp.json()

        return as_json

    def stream_response(self, resp: Response) -> Any:
        buffer = BytesIO()

        try:
            for chunk in resp.iter_bytes():
                buffer.write(chunk)
        finally:
            resp.close()

        return buffer

    def clone(self) -> ContextData:
        return deepcopy(self)


@dataclass
class OperationInfo:
    data: ContextData
    in_progress: bool = False
    last_updated_at: datetime = field(default_factory=datetime.now)
    response: Optional[Any] = None


UpdateFunc = Callable[[OperationInfo], bool]
UpdateResponseFunc = Callable[[OperationInfo, ResponseClass], bool]


class ClientContext:
    def __init__(self, http_client: httpx.Client, data: ContextData) -> None:
        self.http_client: httpx.Client = http_client
        self.data: ContextData = data
        self.timeout: Optional[ClientTimeout] = None

    def build_request(self) -> Request:
        self.data.http_request = self.http_client.build_request(
            method=self.data.method,
            url=self.data.url,
            params=self.data.build_params_arg(),
            json=self.data.build_json_data_arg(),
            data=self.data.build_form_data_arg(),
            files=self.data.file,  # type: ignore[arg-type]
            headers=self.data.headers,
            timeout=DEFAULT_PER_CALL_TIMEOUT,
        )

        return ensure_valid(self.data.http_request)

    def send_request(self) -> Response:
        request = ensure_valid(self.data.http_request)

        for retry in range(1, DEFAULT_RETRY_COUNT + 1):
            try:
                self.data.http_response = self.http_client.send(
                    request=request,
                    stream=self.data.should_stream,
                )
                break
            except (ReadTimeout, WriteTimeout):
                msg = (
                    f"Timeout waiting for {self.data.method.upper()} on {self.data.url}"
                )
                msg += f" (attempt {retry} of {DEFAULT_RETRY_COUNT})"

                if retry < DEFAULT_RETRY_COUNT:
                    print(
                        f"@@@@@@@@@ {msg}. Retrying in {DEFAULT_RETRY_INTERVAL}s..."
                    )  # noqa
                    time.sleep(DEFAULT_RETRY_INTERVAL)
                else:
                    raise Timeout(msg) from None

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

    def build_update_func(
        self,
        update_func: Callable[..., bool],
        response_cls: Optional[Type[ResponseClass]] = None,
    ) -> UpdateFunc:
        if callable_type_match(UpdateFunc, update_func):  # type: ignore[arg-type]

            def call_update_func(info: OperationInfo) -> bool:
                return update_func(info)

        elif callable_type_match(UpdateResponseFunc, update_func):  # type: ignore[arg-type]
            response_cls = ensure_valid(response_cls, "response class")

            def call_update_func(info: OperationInfo) -> bool:
                info.response = self.build_response(response_cls)
                return update_func(info, info.response)

        else:
            raise RuntimeError(
                "Expected a valid 'update_func' function"
                f", got {update_func} instead (response_cls={response_cls})"
            )

        return call_update_func

    def loop_until(
        self,
        *,
        label: str,
        update_func: Callable[..., bool],
        response_cls: Optional[Type[ResponseClass]] = None,
    ) -> OperationInfo:
        call_update_func = self.build_update_func(update_func, response_cls)
        info = OperationInfo(data=self.data)
        last_updated_at = info.last_updated_at
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

            last_updated_duration = (
                info.last_updated_at - last_updated_at
            ).total_seconds()

            if last_updated_duration > DEFAULT_TIMEOUT:
                raise TimeoutError(f"It took more than {DEFAULT_TIMEOUT}s {what_label}")
            else:
                last_updated_at = info.last_updated_at
                logger.info(
                    f"waiting {what_label}"
                    f" (last updated: {info.last_updated_at}"
                    f", duration {last_updated_duration}"
                    f", loop {loops}, sleeping {DEFAULT_RETRY_INTERVAL}s)"
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
        self._http_client = http_client
        self._headers = {"Avatars-Accept-Created": "yes"} | headers

    def set_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    @contextmanager
    def context(
        self, *, ctx: Optional[ClientContext] = None, **kwargs: Any
    ) -> Generator[ClientContext, None, None]:
        http_client = self._http_client or httpx.Client(
            base_url=self.base_url, timeout=self.timeout, verify=self.should_verify_ssl
        )

        # Grab special keys
        headers: dict[str, Any] = pop_or(kwargs, "headers", {})

        if not ctx:
            ctx = ClientContext(
                http_client=http_client,
                data=ContextData(
                    base_url=self.base_url, headers=self._headers.copy(), **kwargs
                ),
            )

        ctx.data.update(**kwargs)
        ctx.data.headers.update(headers)

        yield ctx

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
            response = ctx.build_and_send_request()

            if ctx.data.is_created():
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
            "verify_auth={self.verify_auth})"
        )
