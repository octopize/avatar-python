# This file has been generated - DO NOT MODIFY
# API Version : 0.4.14

import sys
from collections.abc import Mapping, Sequence
from enum import Enum
from io import BytesIO, StringIO
from json import loads as json_loads
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

import httpx
from pydantic import BaseModel

from avatars.api import (
    DEFAULT_TIMEOUT,
    Auth,
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
from avatars.models import ForgottenPasswordRequest, Login, ResetPasswordRequest

MAX_FILE_LENGTH = 1024 * 1024 * 1024


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
    def __init__(self, base_url: str, timeout: Optional[int] = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url

        self.auth = Auth(self)
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
        self._headers = {"User-Agent": "avatar-python"}

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
        form_data: Optional[BaseModel] = None,
        file: Optional[Union[StringIO, BytesIO]] = None,
        timeout: Optional[int] = None,
        **kwargs: Dict[str, Any],
    ) -> Any:
        """Request the API."""

        should_verify = kwargs.get("verify_auth") is None or kwargs.get("verify_auth") == True  # type: ignore
        if should_verify and "Authorization" not in self._headers:
            raise Exception("You are not authenticated.")

        # Custom encoder because UUID is not JSON serializable by httpx
        # and Enums need their value to be sent, e.g. 'int' instead of 'ColumnType.int'
        json_arg = json_loads(json.json(encoder=_default_encoder)) if json else None
        form_data_arg = form_data.dict() if form_data else None

        files_arg = self._get_file_argument(file)

        with httpx.Client(
            timeout=timeout or self.timeout, base_url=self.base_url
        ) as client:
            result = client.request(
                method,
                url,
                params=params,
                json=json_arg,
                data=form_data_arg,
                files=files_arg,
                headers=self._headers,
            )

        if result.status_code != 200:
            json = result.json()
            value = json.get("detail")  # type: ignore
            if (
                result.status_code == 401
                and isinstance(value, str)
                and "authenticated" in value
            ):
                raise Exception("You are not authenticated.")
            standard_error = _get_nested_value(json, "message")  # type: ignore

            if standard_error:
                error_msg = standard_error
            elif validation_error := _get_nested_value(json, "msg"):  # type: ignore
                if detailed_message := _get_nested_value(json, "loc"):  # type: ignore
                    field = detailed_message[-1]
                    error_msg = f"{validation_error}: {field}"
                else:
                    error_msg = f"Bad Request: {validation_error}"
            else:
                error_msg = "Internal error"

            raise Exception(
                f"Got error in HTTP request: {method} {url}. {result.status_code} {error_msg}"
            )

        if result.headers["content-type"] == "application/json":
            return result.json()
        elif result.headers["content-type"] == "application/pdf":
            return result.content
        else:
            return result.text

    def _get_file_argument(
        self, file: Optional[Union[StringIO, BytesIO]]
    ) -> Optional[Dict[str, Tuple[str, bytes, str]]]:

        if not file:
            return None

        filename = str(Path(file.name).name) if hasattr(file, "name") else "file.csv"

        content = file.read(MAX_FILE_LENGTH)

        if sys.getsizeof(content) >= MAX_FILE_LENGTH:
            raise FileTooLarge(
                f"The file size must not exceed{MAX_FILE_LENGTH / 1024 : .0f} MB."
            )

        encoded_content = (
            content if isinstance(content, bytes) else content.encode("utf-8")
        )

        # The dictionary key must be 'file' and you MUST pass in a filename
        # else there is a request ValidationError on the server side
        return {"file": (filename, encoded_content, "text/csv")}
