# This file has been generated - DO NOT MODIFY
# API Version : 1.1.0-8143129ddb2381b96eb92a581856bda578d89291


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
from avatars.base_client import BaseClient
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


class ApiClient(BaseClient):
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
        super().__init__(
            base_url,
            timeout,
            should_verify_ssl,
            verify_auth=verify_auth,
            http_client=http_client,
            headers={"User-Agent": f"avatar-python/{__version__}"},
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

    def __str__(self) -> str:
        return f"ApiClient(base_url={self.base_url}, timeout={self.timeout}, should_verify_ssl={self.should_verify_ssl}, verify_auth={self.verify_auth})"
