"""Tests for ClientConfig model_validator."""

import pytest
from pydantic import HttpUrl

from avatars.client_config import ClientConfig
from avatars.config import Config


class TestClientConfigValidator:
    """Test the construct_urls_from_base model validator."""

    def test_base_url_constructs_api_and_storage_urls(self) -> None:
        """Test that base_url constructs both API and storage URLs."""
        config = ClientConfig(base_url="https://example.com")

        assert str(config.base_api_url) == "https://example.com/api"
        assert str(config.storage_endpoint_url) == "https://example.com/storage"

    def test_base_url_and_explicit_api_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot set BASE_URL together with"):
            ClientConfig(
                base_url="https://example.com",
                base_api_url="https://api.example.com",
            )

    def test_base_url_and_explicit_storage_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot set BASE_URL together with"):
            ClientConfig(
                base_url="https://example.com",
                storage_endpoint_url="https://storage.example.com",
            )

    def test_base_url_and_explicit_storage_and_api_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot set BASE_URL together with"):
            ClientConfig(
                base_url="https://example.com",
                base_api_url="https://api.example.com",
                storage_endpoint_url="https://storage.example.com",
            )

    def test_explicit_urls_without_base_url(self) -> None:
        """Test that explicit API and storage URLs work without base_url."""
        config = ClientConfig(
            base_api_url="https://api.example.com",
            storage_endpoint_url="https://storage.example.com",
        )

        assert str(config.base_api_url) == "https://api.example.com/"
        assert str(config.storage_endpoint_url) == "https://storage.example.com/"
        assert config.base_url is None

    def test_from_config_method(self) -> None:
        """Test that from_config properly converts Config to ClientConfig."""
        # Don't use BASE_URL with Config because it reads from env and may conflict
        env_config = Config(
            _env_file=None,  # Don't load from .env
            BASE_API_URL=HttpUrl("https://api.example.com"),
            STORAGE_ENDPOINT_URL=HttpUrl("https://storage.example.com"),
            TIMEOUT=90,
            SHOULD_VERIFY_SSL=False,
            API_KEY="test-key",
        )

        client_config = ClientConfig.from_config(env_config)

        assert str(client_config.base_api_url) == "https://api.example.com/"
        assert str(client_config.storage_endpoint_url) == "https://storage.example.com/"
        assert client_config.timeout == 90
        assert client_config.should_verify_ssl is False
        assert client_config.api_key == "test-key"
