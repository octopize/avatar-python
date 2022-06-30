# This file has been generated - DO NOT MODIFY
# API Version : 0.3.5

from collections.abc import Mapping, Sequence
from enum import Enum
from io import BytesIO
from json import loads as json_loads
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx
from pydantic import BaseModel

from avatars.api import Auth, Datasets, Health, Jobs, Metrics, Users
from avatars.models import Login


def get_nested_value(
    obj: Union[Mapping, Sequence], key: str, default: Any = None
) -> Any:
    """
    Return value from (possibly) nested key in JSON dictionary.
    """

    if isinstance(obj, Sequence) and not isinstance(obj, str):
        for item in obj:
            return get_nested_value(item, key, default=default)

    if isinstance(obj, Mapping):
        if key in obj:
            return obj[key]
        return get_nested_value(list(obj.values()), key, default=default)

    return default


def default_encoder(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)  # default


DEFAULT_TIMEOUT = 5


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

        self.auth = Auth(self)
        self.datasets = Datasets(self)
        self.health = Health(self)
        self.jobs = Jobs(self)
        self.metrics = Metrics(self)
        self.users = Users(self)

        self._headers = {"User-Agent": "avatar-python"}

    def authenticate(self, username: str, password: str) -> None:
        result = self.auth.login(
            Login(username=username, password=password),
        )
        self._headers["Authorization"] = f"Bearer {result.access_token}"

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[BaseModel] = None,
        form_data: Optional[BaseModel] = None,
        file: Optional[BytesIO] = None,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        **kwargs: Dict[str, Any],
    ) -> Any:
        """Request the API."""

        should_verify = (
            kwargs.get("verify_auth") is None or kwargs.get("verify_auth") == True
        )
        if should_verify and "Authorization" not in self._headers:
            raise Exception("You are not authenticated.")

        # Custom encoder because UUID is not JSON serializable by httpx
        # and Enums need their value to be sent, e.g. 'int' instead of 'ColumnType.int'
        json_arg = json_loads(json.json(encoder=default_encoder)) if json else None
        form_data_arg = form_data.dict() if form_data else None

        filename: str
        try:
            filename = str(Path(file.name).name)  # get basename only
        except AttributeError:
            # file is a memory buffer, not an actual file
            filename = "file.csv"
        # The dictionary key must be 'file' and you MUST pass in a filename
        # else there is a request ValidationError on the server side
        files_arg = {"file": (filename, file, "text/csv")} if file else None

        with httpx.Client(timeout=timeout, base_url=self.base_url) as client:
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
            # We return {'detail': 'Not authenticated'}, which is no list.
            if "auth" in str(result.json()):
                raise Exception("You are not authenticated.")

            error_msg = get_nested_value(
                result.json(), "message", default="Internal error"
            )
            raise Exception(
                f"Got error in HTTP request: {method} {url}. {result.status_code} {error_msg}"
            )

        if result.headers["content-type"] == "application/json":
            return result.json()
        else:
            return result.content
