from __future__ import annotations

from pydantic import BaseModel, HttpUrl, model_validator
from typing_extensions import Self

from avatars.config import Config, construct_urls


class ClientConfig(BaseModel):
    """Configuration for ApiClient and Manager.

    This is a plain dataclass-like configuration that can be:
    1. Created directly with explicit values
    2. Derived from a Config object (which loads from env vars)
    3. Passed to ApiClient or Manager

    Attributes
    ----------
    base_url : HttpUrl | None
        The base URL of the Avatar server.
        Default is None.
    base_api_url : HttpUrl | None
        The base URL of the Avatar API server.
        Default is None.
    timeout : int | None
        Timeout in seconds for API requests.
        Default is None (will use DEFAULT_TIMEOUT if not specified).
    should_verify_ssl : bool
        Whether to verify SSL certificates on the server.
        Default is True.
    storage_endpoint_url : HttpUrl | None
        The storage endpoint URL for file uploads/downloads.
        Default is None (must be provided for ApiClient).
    api_key : str | None
        Optional API key for authentication. When provided, this will be used
        instead of username/password authentication.
    """

    base_url: HttpUrl | None = None
    base_api_url: HttpUrl | None = None
    storage_endpoint_url: HttpUrl | None = None

    timeout: int | None = None
    should_verify_ssl: bool = True
    api_key: str | None = None

    @classmethod
    def from_config(cls, config: Config) -> ClientConfig:
        """Convert this Config to a ClientConfig.

        This method extracts the relevant fields from the environment-aware Config
        and creates a ClientConfig that can be passed to ApiClient or Manager.

        Returns
        -------
        ClientConfig
            A new ClientConfig instance with values from this Config.
        """
        # model_construct because we don't want to apply the validators again
        return ClientConfig.model_construct(
            base_url=config.BASE_URL,
            base_api_url=config.BASE_API_URL,
            timeout=config.TIMEOUT,
            should_verify_ssl=config.SHOULD_VERIFY_SSL,
            storage_endpoint_url=config.STORAGE_ENDPOINT_URL,
            api_key=config.API_KEY,
        )

    @model_validator(mode="after")
    def construct_urls_from_base(self) -> Self:
        """Construct API and storage URLs based on BASE_URL if provided.

        This validator runs after model initialization to ensure that
        BASE_API_URL and STORAGE_ENDPOINT_URL are correctly set based
        on BASE_URL if it is provided.

        Returns
        -------
        Self
            The validated Config instance with constructed URLs.
        """
        api_url, storage_url = construct_urls(
            base_url=self.base_url,
            base_api_url=self.base_api_url,
            storage_endpoint_url=self.storage_endpoint_url,
            # We do not want to use defaults here.
            # We shall use from_config to get defaults from Config if needed.
            use_defaults=False,
        )
        self.base_api_url = api_url
        self.storage_endpoint_url = storage_url
        return self
