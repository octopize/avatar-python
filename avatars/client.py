# This file has been generated - DO NOT MODIFY
# API Version : 11.7.0

import warnings
from dataclasses import dataclass
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
    LoginResponse,
    ResetPasswordRequest,
)

MAX_FILE_LENGTH = 1024 * 1024 * 1024  # 1 GB


@dataclass
class AuthTokens:
    access: str
    refresh: Optional[str] = None

    def update(self, resp: LoginResponse) -> None:
        self.access = resp.access_token

        if resp.refresh_token:
            self.refresh = resp.refresh_token


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
            on_auth_refresh=self._refresh_auth,
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
        self.auth_tokens: Optional[AuthTokens] = None

        # Verify client is compatible with the server
        if should_verify_compatibility:
            response = self.compatibility.is_client_compatible()

            uncompatible_statuses = [
                CompatibilityStatus.incompatible,
                CompatibilityStatus.unknown,
            ]
            if response.status in uncompatible_statuses:
                compat_error_message = "Client is not compatible with the server.\n"
                compat_error_message += f"Server message: {response.message}.\n"
                compat_error_message += f"Client version: {__version__}.\n"

                compat_error_message += "Most recent compatible client version: "
                compat_error_message += f"{response.most_recent_compatible_client}.\n"

                compat_error_message += "To update your client, you can run "
                compat_error_message += "`pip install --upgrade octopize.avatar`.\n"

                compat_error_message += "To ignore, you can set "
                compat_error_message += (
                    "`ApiClient(should_verify_compatibility=False)`."
                )
                warnings.warn(compat_error_message)
                raise DeprecationWarning(compat_error_message)

    def authenticate(
        self, username: str, password: str, timeout: Optional[int] = None
    ) -> None:
        resp = self.auth.login(
            Login(username=username, password=password),
            timeout=timeout or self.timeout,
        )
        self._update_auth_tokens(resp)

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

    def _enable_refresh_auth(self, enable: bool = True) -> None:
        self.on_auth_refresh(self._refresh_auth if enable else None)

    def _refresh_auth(self) -> dict[str, str]:
        new_headers: dict[str, str] = {}

        if self.auth_tokens:
            if self.auth_tokens.refresh:
                resp = self.auth.refresh(self.auth_tokens.refresh)
                self._update_auth_tokens(resp, headers=new_headers)
            else:
                warnings.warn("Cannot refresh auth with refresh token")
        else:
            warnings.warn("Client is not authenticated, cannot refresh auth")

        return new_headers

    def _set_auth_bearer(
        self, token: str, *, headers: Optional[dict[str, str]] = None
    ) -> None:
        self.set_header("Authorization", f"Bearer {token}")

        if headers is not None:
            headers["Authorization"] = f"Bearer {token}"

    def _update_auth_tokens(
        self, resp: LoginResponse, *, headers: Optional[dict[str, str]] = None
    ) -> None:
        if not self.auth_tokens:
            self.auth_tokens = AuthTokens(
                access=resp.access_token, refresh=resp.refresh_token
            )
        else:
            self.auth_tokens.update(resp)

        self._set_auth_bearer(self.auth_tokens.access, headers=headers)
