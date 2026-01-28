# This file has been generated - DO NOT MODIFY
# API Version : 2.44.0

import warnings
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import httpx
from structlog import get_logger

from avatars import __version__
from avatars.base_client import BaseClient
from avatars.client_config import ClientConfig
from avatars.constants import DEFAULT_TIMEOUT
from avatars.models import (
    ForgottenPasswordRequest,
    Login,
    LoginResponse,
    ResetPasswordRequest,
)

MAX_FILE_LENGTH = 1024 * 1024 * 1024  # 1 GB

logger = get_logger(__name__)


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
        base_url: str | None = None,
        *,
        timeout: int | None = None,
        should_verify_ssl: bool | None = None,
        verify_auth: bool = True,
        http_client: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
        config: ClientConfig | None = None,
    ) -> None:
        """Client to communicate with the Avatar API.

        Parameters
        ----------
        base_url:
            url of the API (required if config not provided)
        timeout:
            timeout in seconds, by default None (uses DEFAULT_TIMEOUT)
        should_verify_ssl : optional
            whether to verify SSL certificates on the server. By default None (uses True)
        http_client : optional
            allow passing in custom httpx.Client instance, by default None
        verify_auth : optional
            Bypass client-side authentication verification, by default True
        api_key : optional
            API key for authentication using api-key-v1 scheme. If provided,
            authenticate() should not be called. By default None
        config : optional
            ClientConfig object containing all configuration.
            Mutually exclusive individual parameters (except http_client).
            By default None
        """
        if config is not None:
            conflicting_params = []
            if base_url is not None:
                conflicting_params.append("base_url")
            if timeout is not None:
                conflicting_params.append("timeout")
            if should_verify_ssl is not None:
                conflicting_params.append("should_verify_ssl")
            if api_key is not None:
                conflicting_params.append("api_key")

            if conflicting_params:
                params_str = ", ".join(conflicting_params)
                raise ValueError(
                    f"Cannot provide both 'config' and other parameters ({params_str}). "
                    "Either pass a ClientConfig object or individual parameters, not both. "
                    "Note: 'http_client' is allowed alongside 'config' for testing."
                )
        else:
            # Create ClientConfig from individual parameters

            if not base_url:
                raise ValueError("base_url must be provided when creating an ApiClient")

            if '"' in base_url:
                raise ValueError(
                    f"Expected base_url not to contain quotes. Got {base_url} instead"
                )

            # Try to derive from base_url (replace /api with /storage)
            if not base_url.endswith("/api"):
                raise ValueError("base_url must end with '/api' to derive storage_endpoint_url")

            final_storage_url = base_url.replace("/api", "/storage")

            config = ClientConfig(
                base_api_url=base_url,
                timeout=timeout,
                should_verify_ssl=(should_verify_ssl if should_verify_ssl is not None else True),
                storage_endpoint_url=final_storage_url,
                api_key=api_key,
            )

        if config.base_api_url is None:
            raise ValueError("base_api_url must be set in ClientConfig")

        final_timeout = config.timeout if config.timeout is not None else DEFAULT_TIMEOUT

        super().__init__(
            base_url=str(config.base_api_url),
            timeout=final_timeout,
            should_verify_ssl=config.should_verify_ssl,
            verify_auth=verify_auth,
            on_auth_refresh=self._refresh_auth if not config.api_key else None,
            http_client=http_client,
            headers={"User-Agent": f"avatar-python/{__version__}"},
            api_key=config.api_key,
        )

        # Importing here to prevent circular import
        from avatars.api import (
            ApiKeys,
            Auth,
            Compatibility,
            Health,
            Jobs,
            Openapi,
            Resources,
            Results,
            Users,
        )
        from avatars.data_upload import DataUploader

        self.api_keys = ApiKeys(self)
        self.auth = Auth(self)
        self.compatibility = Compatibility(self)
        self.health = Health(self)
        self.jobs = Jobs(self)
        self.openapi = Openapi(self)
        self.resources = Resources(self)
        self.results = Results(self)
        self.users = Users(self)

        data_uploader = DataUploader(
            self,
            should_verify_ssl=config.should_verify_ssl,
            storage_endpoint_url=str(config.storage_endpoint_url),
        )
        self.data_uploader = data_uploader
        self.upload_file = data_uploader.upload_file
        self.download_file = data_uploader.download_file

        self.auth_tokens: Optional[AuthTokens] = None

        logger.debug("ApiClient initialized", base_api_url=str(config.base_api_url))

    def authenticate(self, username: str, password: str, timeout: Optional[int] = None) -> None:
        if self._api_key:
            raise ValueError(
                "Cannot call authenticate() when api_key is set. "
                "API key authentication is already active. "
                "To use username/password authentication, create a new ApiClient without api_key."
            )

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

        # API keys don't expire, no refresh needed
        if self._api_key:
            return new_headers

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
