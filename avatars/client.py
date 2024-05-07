# This file has been generated - DO NOT MODIFY
# API Version : 2.0.0-f729943514b3f36aca26f40f15f20380f9d53cbf


import warnings
from typing import Optional
from uuid import UUID

import httpx

from avatars import __version__
from avatars.base_client import BaseClient
from avatars.constants import DEFAULT_TIMEOUT
from avatars.models import (
    CompatibilityStatus,
    ForgottenPasswordRequest,
    Login,
    ResetPasswordRequest,
)

MAX_FILE_LENGTH = 1024 * 1024 * 1024  # 1 GB


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
                    f"Most recent compatible client version: {response.most_recent_compatible_client}.\n"  # noqa: E501
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
        return ", ".join(
            f"ApiClient(base_url={self.base_url}"
            f"timeout={self.timeout}"
            f"should_verify_ssl={self.should_verify_ssl}"
            f"verify_auth={self.verify_auth})"
        )
