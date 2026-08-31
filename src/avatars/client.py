# This file has been generated - DO NOT MODIFY
# API Version : 3.6.0


import httpx
from structlog import get_logger

from avatars import __version__
from avatars.base_client import BaseClient
from avatars.client_config import ClientConfig
from avatars.constants import DEFAULT_TIMEOUT

MAX_FILE_LENGTH = 1024 * 1024 * 1024  # 1 GB

logger = get_logger(__name__)


class ApiClient(BaseClient):
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: int | None = None,
        should_verify_ssl: bool | None = None,
        verify_auth: bool = True,
        http_client: httpx.Client | None = None,
        api_key: str | None = None,
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
            API key for authentication using api-key-v1 scheme. By default None
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
            http_client=http_client,
            headers={"User-Agent": f"avatar-python/{__version__}"},
            api_key=config.api_key,
        )

        # Importing here to prevent circular import
        from avatars.api import (  # noqa: PLC0415
            ApiKeys,
            Compatibility,
            EventLogs,
            Health,
            Jobs,
            Openapi,
            Resources,
            Results,
            Users,
        )
        from avatars.data_upload import DataUploader  # noqa: PLC0415

        self.api_keys = ApiKeys(self)
        self.compatibility = Compatibility(self)
        self.event_logs = EventLogs(self)
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

        logger.debug("ApiClient initialized", base_api_url=str(config.base_api_url))

    def __str__(self) -> str:
        return ", ".join(
            f"ApiClient(base_url={self.base_url}"
            f"timeout={self.timeout}"
            f"should_verify_ssl={self.should_verify_ssl}"
            f"verify_auth={self.verify_auth})"
        )
