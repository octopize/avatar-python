import pytest
from pydantic import HttpUrl

from avatars.config import Config


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all AVATAR-related environment variables."""
    env_vars = [
        "AVATAR_BASE_URL",
        "AVATAR_BASE_API_URL",
        "AVATAR_STORAGE_ENDPOINT_URL",
        "STORAGE_ENDPOINT_URL",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


class TestConfig:
    """Tests for the Config class."""


class TestVerifyCompatibility:
    def test_default_verify_compatibility(self) -> None:
        """Test that VERIFY_COMPATIBILITY defaults to True."""
        config = Config()
        assert config.VERIFY_COMPATIBILITY is True

    def test_verify_compatibility_from_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that VERIFY_COMPATIBILITY can be set to True via env var."""
        monkeypatch.setenv("AVATAR_VERIFY_COMPATIBILITY", "true")
        config = Config()
        assert config.VERIFY_COMPATIBILITY is True

    def test_verify_compatibility_from_env_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that VERIFY_COMPATIBILITY can be set to False via env var."""
        monkeypatch.setenv("AVATAR_VERIFY_COMPATIBILITY", "false")
        config = Config()
        assert config.VERIFY_COMPATIBILITY is False


class TestStorageEndpointURL:
    """Tests for STORAGE_ENDPOINT_URL configuration."""

    def test_default_storage_endpoint_url(self, clean_env: None) -> None:
        """Test that STORAGE_ENDPOINT_URL defaults to the SaaS URL."""
        config = Config()
        assert str(config.STORAGE_ENDPOINT_URL) == "https://www.octopize.app/storage"

    @pytest.mark.parametrize(
        "env_name",
        [
            "AVATAR_STORAGE_ENDPOINT_URL",
            "STORAGE_ENDPOINT_URL",  # backwards compatibility
        ],
    )
    def test_storage_endpoint_url_from_env(
        self, env_name: str, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that STORAGE_ENDPOINT_URL can be set via env var multiple ways."""
        test_url = "https://storage.example.com"
        monkeypatch.setenv(env_name, test_url)
        config = Config()
        # HttpUrl adds trailing slash
        assert str(config.STORAGE_ENDPOINT_URL) == test_url + "/"


class TestBaseURLConstruction:
    """Tests for BASE_URL construction of API and storage URLs."""

    def test_base_url_from_env(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that BASE_URL can be set via environment variable."""
        monkeypatch.setenv("AVATAR_BASE_URL", "https://env.example.com")
        config = Config()
        assert str(config.BASE_API_URL) == "https://env.example.com/api"
        assert str(config.STORAGE_ENDPOINT_URL) == "https://env.example.com/storage"

    def test_explicit_base_api_url_without_base_url(self, clean_env: None) -> None:
        """Test that BASE_API_URL can be set explicitly without BASE_URL."""
        config = Config(BASE_API_URL=HttpUrl("https://custom-api.example.com"))
        assert str(config.BASE_API_URL) == "https://custom-api.example.com/"
        assert str(config.STORAGE_ENDPOINT_URL) == "https://www.octopize.app/storage"

    def test_explicit_storage_url_without_base_url(self, clean_env: None) -> None:
        """Test that STORAGE_ENDPOINT_URL can be set explicitly without BASE_URL."""
        config = Config(STORAGE_ENDPOINT_URL=HttpUrl("https://custom-storage.example.com"))
        assert str(config.BASE_API_URL) == "https://www.octopize.app/api"
        assert str(config.STORAGE_ENDPOINT_URL) == "https://custom-storage.example.com/"

    def test_explicit_both_urls_without_base_url(self, clean_env: None) -> None:
        """Test that both URLs can be set explicitly without BASE_URL."""
        config = Config(
            BASE_API_URL=HttpUrl("https://custom-api.example.com"),
            STORAGE_ENDPOINT_URL=HttpUrl("https://custom-storage.example.com"),
        )
        assert str(config.BASE_API_URL) == "https://custom-api.example.com/"
        assert str(config.STORAGE_ENDPOINT_URL) == "https://custom-storage.example.com/"

    def test_base_url_with_base_api_url_raises_error(self, clean_env: None) -> None:
        """Test that setting both BASE_URL and BASE_API_URL raises ValueError."""
        with pytest.raises(ValueError, match="Cannot set BASE_URL together with"):
            Config(
                BASE_URL=HttpUrl("https://example.com"),
                BASE_API_URL=HttpUrl("https://api.example.com"),
            )

    def test_base_url_with_storage_url_raises_error(self, clean_env: None) -> None:
        """Test that setting both BASE_URL and STORAGE_ENDPOINT_URL raises ValueError."""
        with pytest.raises(ValueError, match="Cannot set BASE_URL together with"):
            Config(
                BASE_URL=HttpUrl("https://example.com"),
                STORAGE_ENDPOINT_URL=HttpUrl("https://storage.example.com"),
            )

    def test_base_url_with_both_urls_raises_error(self, clean_env: None) -> None:
        """Test that setting BASE_URL with both other URLs raises ValueError."""
        with pytest.raises(ValueError, match="Cannot set BASE_URL together with"):
            Config(
                BASE_URL=HttpUrl("https://example.com"),
                BASE_API_URL=HttpUrl("https://api.example.com"),
                STORAGE_ENDPOINT_URL=HttpUrl("https://storage.example.com"),
            )
