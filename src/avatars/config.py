from pydantic import AliasChoices, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

UNCONFIGURED = "unconfigured"

DEFAULT_API_URL = "https://www.octopize.app/api"
DEFAULT_STORAGE_URL = "https://www.octopize.app/storage"

DEFAULT_CRASH_REPORT_PATH = "crash_report.txt"


def construct_urls(
    base_url: HttpUrl | None = None,
    base_api_url: HttpUrl | None = None,
    storage_endpoint_url: HttpUrl | None = None,
    use_defaults: bool = True,
) -> tuple[HttpUrl | None, HttpUrl | None]:
    """Construct API and storage URLs from configuration values.

    Ensures that either BASE_URL is used to construct both URLs,
    or BASE_API_URL and STORAGE_ENDPOINT_URL are explicitly set.
    Mixing the two patterns is not allowed.

    Parameters
    ----------
    base_url : HttpUrl | None
        The base URL to construct API and storage URLs from.
    base_api_url : HttpUrl | None
        The explicit API URL.
    storage_endpoint_url : HttpUrl | None
        The explicit storage endpoint URL.

    Returns
    -------
        A tuple of (base_api_url, storage_endpoint_url).

    Raises
    ------
    ValueError
        If BASE_URL is set together with BASE_API_URL or STORAGE_ENDPOINT_URL.
    """
    base_url_set = base_url is not None
    api_url_set = base_api_url is not None
    storage_url_set = storage_endpoint_url is not None

    # Case 1: BASE_URL is set, construct the other URLs
    if base_url_set:
        if api_url_set or storage_url_set:
            raise ValueError(
                "Cannot set BASE_URL together with BASE_API_URL or "
                "STORAGE_ENDPOINT_URL. Either use BASE_URL alone, or set "
                "BASE_API_URL and STORAGE_ENDPOINT_URL explicitly."
            )
        # Construct URLs from BASE_URL
        base = str(base_url).rstrip("/")
        return HttpUrl(f"{base}/api"), HttpUrl(f"{base}/storage")

    # Case 2: Individual URLs are set (or use defaults)
    if use_defaults:
        base_api_url = base_api_url or HttpUrl(DEFAULT_API_URL)
        storage_endpoint_url = storage_endpoint_url or HttpUrl(DEFAULT_STORAGE_URL)

    return base_api_url, storage_endpoint_url


class Config(BaseSettings):
    """Configuration settings for the Avatar client.

    This configuration class supports automatic loading from environment variables.
    When both environment variables and explicit Config object values are set,
    the explicitly provided values take precedence.

    Attributes
    ----------
    BASE_API_URL : str
        The base URL of the Avatar API server.
        Default is "http://www.octopize.app/api" for SaaS server.
    TIMEOUT : int
        Timeout in seconds for API requests.
        Default is 5 seconds.
    SHOULD_VERIFY_SSL : bool
        Whether to verify SSL certificates on the server.
        Default is True.
    STORAGE_ENDPOINT_URL : str
        The storage endpoint URL for file uploads/downloads.
        Default is "http://www.octopize.app/storage" for SaaS server.
    VERIFY_COMPATIBILITY : bool
        Whether to verify client-server compatibility on authentication.
        Default is True.
    API_KEY : str | None
        Optional API key for authentication. When provided, this will be used
        instead of username/password authentication. Can be set via the
        AVATAR_API_KEY environment variable.

    Notes
    -----

    Add the AVATAR_ prefix to environment variables to set these values from the environment.

    To override configuration values in tests or code, pass them as keyword arguments:
        config = Config(BASE_API_URL="https://test.com", VERIFY_COMPATIBILITY=False)
    """

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="AVATAR_",
    )
    BASE_URL: HttpUrl | None = None
    BASE_API_URL: HttpUrl | None = None
    TIMEOUT: int = 60
    SHOULD_VERIFY_SSL: bool = True
    STORAGE_ENDPOINT_URL: HttpUrl | None = Field(
        default=None,
        # Allow the environment variable to be set without prefix for backward compatibility
        validation_alias=AliasChoices("STORAGE_ENDPOINT_URL", "AVATAR_STORAGE_ENDPOINT_URL"),
    )
    VERIFY_COMPATIBILITY: bool = True
    API_KEY: str | None = None
    CRASH_REPORT_PATH: str = DEFAULT_CRASH_REPORT_PATH

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
            base_url=self.BASE_URL,
            base_api_url=self.BASE_API_URL,
            storage_endpoint_url=self.STORAGE_ENDPOINT_URL,
        )
        self.BASE_API_URL = api_url
        self.STORAGE_ENDPOINT_URL = storage_url
        return self


def get_config() -> Config:
    return Config()


config: Config = get_config()
