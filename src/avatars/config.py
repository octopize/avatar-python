import os

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILENAME = os.environ.get("DOTENV", "")

UNCONFIGURED = "unconfigured"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        # https://pydantic-docs.helpmanual.io/usage/settings/#use-case-docker-secrets
        env_file=[ENV_FILENAME],
        extra="ignore",
    )

    STORAGE_ENDPOINT_URL: HttpUrl = HttpUrl(
        os.environ.get("STORAGE_ENDPOINT_URL", "https://storage-scaleway-prod.octopize.app")
    )


def get_config() -> Config:
    """Get the config."""
    return Config()


config: Config = get_config()
