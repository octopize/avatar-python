# This file has been generated - DO NOT MODIFY
# API Version : 0.5.24-9abafdba2efbeee858fcabff049b56b18a218e9e


import sys
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from enum import Enum
from io import BytesIO, StringIO
from json import loads as json_loads
from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    BinaryIO,
    Dict,
    Generator,
    Literal,
    Optional,
    Protocol,
    Sequence,
    TextIO,
    Tuple,
    Union,
    cast,
    overload,
)
from uuid import UUID

import httpx
from httpx import ReadTimeout, Response, WriteTimeout
from pydantic import BaseModel
from toolz.dicttoolz import valfilter, valmap
from typing_extensions import TypeAlias, TypeGuard

from avatars import __version__
from avatars.constants import DEFAULT_TIMEOUT
from avatars.exceptions import FileTooLarge, Timeout
from avatars.models import ForgottenPasswordRequest, Login, ResetPasswordRequest

MAX_FILE_LENGTH = 1024 * 1024 * 1024  # 1 GB


if TYPE_CHECKING:
    from avatars._typing import FileLikeInterface, HttpxFile

from avatars._typing import is_file_like


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


def _default_encoder(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)  # default


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        should_verify_ssl: bool = True,
        *,
        verify_auth: bool = True,
        http_client: Optional[httpx.Client] = None,
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
        self.base_url = base_url

        if '"' in self.base_url:
            raise ValueError(
                "Expected base_url not to contain quotes. Got {self.base_url} instead"
            )

        # Importing here to prevent circular import
        from avatars.api import (
            Auth,
            Compatibility,
            Datasets,
            Health,
            Jobs,
            Metrics,
            PandasIntegration,
            Pipelines,
            Reports,
            Stats,
            Users,
        )

        self.auth = Auth(self)
        self.compatibility = Compatibility(self)
        self.datasets = Datasets(self)
        self.health = Health(self)
        self.jobs = Jobs(self)
        self.metrics = Metrics(self)
        self.reports = Reports(self)
        self.stats = Stats(self)
        self.users = Users(self)

        self.pandas_integration = PandasIntegration(self)
        self.pipelines = Pipelines(self)

        self.timeout = timeout
        self.should_verify_ssl = should_verify_ssl
        self._http_client = http_client
        self.verify_auth = verify_auth
        self._headers = {"User-Agent": f"avatar-python/{__version__}"}

    @contextmanager
    def _get_http_client(self) -> Generator[httpx.Client, None, None]:
        if self._http_client:
            yield self._http_client
        else:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                verify=self.should_verify_ssl,
            ) as client:
                yield client

    def authenticate(
        self, username: str, password: str, timeout: Optional[int] = None
    ) -> None:
        result = self.auth.login(
            Login(username=username, password=password),
            timeout=timeout or self.timeout,
        )
        self._headers["Authorization"] = f"Bearer {result.access_token}"

    def forgotten_password(self, email: str, timeout: Optional[int] = None) -> None:
        self.auth.forgotten_password(
            ForgottenPasswordRequest(email=email), timeout=timeout or self.timeout
        )

    def reset_password(
        self,
        email: str,
        new_password: str,
        new_password_repeated: str,
        token: UUID,
        timeout: Optional[int] = None,
    ) -> None:
        self.auth.reset_password(
            ResetPasswordRequest(
                email=email,
                new_password=new_password,
                new_password_repeated=new_password_repeated,
                token=token,
            ),
            timeout=timeout or self.timeout,
        )

    def handle_response(
        self,
        response: httpx.Response,
        *,
        should_stream: bool,
    ) -> Any:
        if should_stream:
            return self._handle_streaming_response(response)
        else:
            return self._handle_standard_response(response)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[BaseModel] = None,
        form_data: Optional[Union[BaseModel, Dict[str, Any]]] = None,
        file: Optional[Sequence["HttpxFile"]] = None,
        timeout: Optional[int] = None,
        should_verify_auth: bool = True,
        **kwargs: Dict[str, Any],
    ) -> Any:
        """Request the API."""

        should_verify = self.verify_auth and should_verify_auth

        if should_verify and "Authorization" not in self._headers:
            raise Exception("You are not authenticated.")

        should_stream = bool(kwargs.get("should_stream", False))  # for download

        with self._get_http_client() as client:
            request = build_request(
                client,
                method=method,
                url=url,
                params=params,
                json=json,
                form_data=form_data,
                file=file,
                timeout=timeout or self.timeout,
                headers=self._headers,
            )

            response = send_request(
                client, request=request, should_stream=should_stream
            )

            return self.handle_response(response, should_stream=should_stream)

    def _handle_standard_response(
        self, result: Response
    ) -> Union[Dict[str, Any], bytes, str]:
        if not result.is_success:
            _raise_on_status(result, result.json())

        if result.headers["content-type"] == "application/json":
            as_json: Dict[str, Any] = result.json()
            return as_json
        elif result.headers["content-type"] in (
            "application/pdf",
            "application/octet-stream",
        ):
            return result.content
        else:
            return result.text

    def _handle_streaming_response(self, result: Response) -> BytesIO:
        if not result.is_success:
            content = result.read()
            encoding = result.encoding or "utf-8"
            as_json: Dict[str, Any] = json_loads(content.decode(encoding))
            _raise_on_status(result, as_json)

        buffer = BytesIO()
        try:
            for chunk in result.iter_bytes():
                buffer.write(chunk)
        finally:
            result.close()

        return buffer

    def __str__(self) -> str:
        return f"ApiClient(base_url={self.base_url}, timeout={self.timeout}, should_verify_ssl={self.should_verify_ssl}, verify_auth={self.verify_auth})"


def handle_response_failure(response: Response, *, should_stream: bool) -> None:
    """
    Handle the failure of a response.

    This needs the httpx.Client instance to remain open, even though no client
    is used in this function.
    """
    if response.is_success:
        raise ValueError("Response is not a failure.")

    as_json: Dict[str, Any] = {}
    try:
        content = response.read()
    except httpx.StreamConsumed:
        as_json = response.json()
    else:
        encoding = response.encoding or "utf-8"
        as_json = json_loads(content.decode(encoding))

    _raise_on_status(response, as_json)


@overload
def handle_response_stream(response: Response, destination: None) -> bytes:
    ...


@overload
def handle_response_stream(
    response: Response, destination: "FileLikeInterface[bytes]"
) -> None:
    ...


def handle_response_stream(
    response: Response, destination: Optional["FileLikeInterface[bytes]"] = None
) -> Optional[bytes]:
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
    _destination: "FileLikeInterface[bytes]" = destination or BytesIO()

    try:
        for chunk in response.iter_bytes():
            _destination.write(chunk)
    finally:
        response.close()

    if not destination:
        return _destination.read()

    return None


def _raise_on_status(result: Response, content: Dict[str, Any]) -> None:
    value = content.get("detail")
    if (
        result.status_code == 401
        and isinstance(value, str)
        and "authenticated" in value
    ):
        raise Exception("You are not authenticated.")
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
        f"Got error in HTTP request: {result.request.method} {result.request.url}. Error status {result.status_code} - {error_msg}"
    )


def build_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[BaseModel] = None,
    form_data: Optional[Union[BaseModel, Dict[str, Any]]] = None,
    file: Optional[Sequence["HttpxFile"]] = None,
    headers: Dict[str, Any] = {},
    timeout: Optional[int] = DEFAULT_TIMEOUT,
) -> httpx.Request:
    # Remove params if they are set to None (allow handling of optionals)
    if isinstance(params, dict):
        params = valfilter(lambda x: x is not None, params)
        params = valmap(lambda x: x.value if isinstance(x, Enum) else x, params)

    json_arg = json_loads(json.model_dump_json()) if json else None
    form_data_arg = (
        form_data.model_dump() if isinstance(form_data, BaseModel) else form_data
    )

    if form_data_arg:
        form_data_arg = valfilter(lambda x: x is not None, form_data_arg)
        form_data_arg = valmap(
            lambda x: x.value if isinstance(x, Enum) else x, form_data_arg
        )

    return client.build_request(
        method=method,
        url=url,
        params=params,
        json=json_arg,
        data=form_data_arg,
        files=file,  # type: ignore[arg-type]
        headers=headers,
        timeout=timeout,
    )


def send_request(
    client: httpx.Client, request: httpx.Request, *, should_stream: bool
) -> httpx.Response:
    try:
        return client.send(
            request=request,
            stream=should_stream,
        )
    except (WriteTimeout, ReadTimeout):
        raise Timeout(
            "The call timed out. Consider increasing the timeout with the `timeout` parameter."
        ) from None
