# This file has been generated - DO NOT MODIFY
# API Version : 0.5.24-31ecf491edf177802dac8778b7df365abb92d4d3


import sys
import warnings
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
from avatars.api import (
    DEFAULT_TIMEOUT,
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
    Timeout,
    Users,
)
from avatars.models import (
    CompatibilityStatus,
    ForgottenPasswordRequest,
    Login,
    ResetPasswordRequest,
)

MAX_FILE_LENGTH = 1024 * 1024 * 1024  # 1 GB


if TYPE_CHECKING:
    from avatars._typing import FileLikeInterface, HttpxFile

from avatars._typing import is_file_like


class FileTooLarge(Exception):
    pass


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
        should_verify_compatibility: bool = True,
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

        # Verify client is compatible with the server
        if should_verify_compatibility:
            response = self.compatibility.is_client_compatible()

            uncompatible_statuses = [
                CompatibilityStatus.incompatible,
                CompatibilityStatus.unknown,
            ]
            if response.status in uncompatible_statuses:
                warnings.warn(
                    f"Client is not compatible with the server. \n"
                    f"Server message: {response.message}.\n"
                    f"Current client version: {__version__}.\n"
                    f"Most recent compatible client version: {response.most_recent_compatible_client}.\n"
                )

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

        should_stream = bool(kwargs.get("should_stream", False))  # for download

        with self._get_http_client() as client:
            request = client.build_request(
                method=method,
                url=url,
                params=params,
                json=json_arg,
                data=form_data_arg,
                files=file,  # type: ignore[arg-type]
                headers=self._headers,
                timeout=timeout or self.timeout,
            )
            try:
                result = client.send(
                    request=request,
                    stream=should_stream,
                )

                if should_stream:
                    return self._handle_streaming_response(result)
                else:
                    return self._handle_standard_response(result)
            except (WriteTimeout, ReadTimeout):
                raise Timeout(
                    "The call timed out. Consider increasing the timeout with the `timeout` parameter."
                ) from None

    def _handle_standard_response(
        self, result: Response
    ) -> Union[Dict[str, Any], bytes, str]:
        if not result.is_success:
            self._raise_on_status(result, result.json())

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
            self._raise_on_status(result, as_json)

        buffer = BytesIO()
        try:
            for chunk in result.iter_bytes():
                buffer.write(chunk)
        finally:
            result.close()

        return buffer

    def _raise_on_status(self, result: Response, content: Dict[str, Any]) -> None:
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

    def __str__(self) -> str:
        return f"ApiClient(base_url={self.base_url}, timeout={self.timeout}, should_verify_ssl={self.should_verify_ssl}, verify_auth={self.verify_auth})"
