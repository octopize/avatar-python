# This file has been generated - DO NOT MODIFY
# API Version : 0.20.0

import warnings
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import httpx

from avatars import __version__
from avatars.base_client import BaseClient
from avatars.constants import DEFAULT_TIMEOUT
from avatars.models import (
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
            Datasets,
            Health,
            Jobs,
            Openapi,
            Resources,
            Results,
            Users,
        )
        from avatars.data_upload import DataUploader

        self.auth = Auth(self)
        self.datasets = Datasets(self)
        self.health = Health(self)
        self.jobs = Jobs(self)
        self.openapi = Openapi(self)
        self.resources = Resources(self)
        self.results = Results(self)
        self.users = Users(self)
        self.upload_file = DataUploader(self).upload_file
        self.download_file = DataUploader(self).download_file

        self.auth_tokens: Optional[AuthTokens] = None

    def authenticate(self, username: str, password: str, timeout: Optional[int] = None) -> None:
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

    def _set_auth_bearer(self, token: str, *, headers: Optional[dict[str, str]] = None) -> None:
        self.set_header("Authorization", f"Bearer {token}")

        if headers is not None:
            headers["Authorization"] = f"Bearer {token}"

    def _update_auth_tokens(
        self, resp: LoginResponse, *, headers: Optional[dict[str, str]] = None
    ) -> None:
        if not self.auth_tokens:
            self.auth_tokens = AuthTokens(access=resp.access_token, refresh=resp.refresh_token)
        else:
            self.auth_tokens.update(resp)

        self._set_auth_bearer(self.auth_tokens.access, headers=headers)
