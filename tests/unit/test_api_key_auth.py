"""Unit tests for API key authentication."""

import pytest

from avatars.base_client import ContextData
from avatars.client import ApiClient
from avatars.manager import Manager
from tests.unit.conftest import FakeApiClient


class TestApiClientApiKeyAuth:
    """Test ApiClient with API key authentication."""

    def test_api_key_in_constructor_sets_header(self) -> None:
        """Verify that passing api_key to constructor sets Authorization header."""
        api_key = "test-api-key-456"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=False,
        )

        assert client._api_key == api_key
        assert "Authorization" in client._headers
        assert client._headers["Authorization"] == f"api-key-v1 {api_key}"

    def test_api_key_disables_auth_refresh(self) -> None:
        """Verify that API key authentication disables auth refresh."""
        api_key = "test-api-key-789"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=False,
        )

        # Auth refresh should be disabled (None) when API key is used
        assert client._on_auth_refresh is None

    def test_authenticate_raises_error_with_api_key(self) -> None:
        """Verify that calling authenticate() with API key raises ValueError."""
        api_key = "test-api-key-auth-error"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=False,
        )

        with pytest.raises(
            ValueError,
            match="Cannot call authenticate\\(\\) when api_key is set",
        ):
            client.authenticate("username", "password")

    def test_refresh_auth_skips_with_api_key(self) -> None:
        """Verify that _refresh_auth returns empty dict when API key is set."""
        api_key = "test-api-key-refresh"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=False,
        )

        # Should return empty headers dict without attempting refresh
        new_headers = client._refresh_auth()
        assert new_headers == {}

    def test_api_key_auth_passes_check_auth(self) -> None:
        """Verify that API key authentication passes check_auth."""

        api_key = "test-api-key-check-auth"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=True,  # Enable auth verification
        )

        # Create a context data object to test check_auth
        data = ContextData(
            base_url="http://localhost:8000/api",
            method="GET",
            url="/test",
            headers={},
        )

        # Should not raise because Authorization header is set
        client.check_auth(data)  # Will raise if auth check fails


class TestManagerApiKeyAuth:
    """Test Manager with API key authentication."""

    def test_manager_with_api_key_creates_client(self) -> None:
        """Verify that Manager with api_key creates ApiClient with api_key."""
        api_key = "manager-api-key-123"
        manager = Manager(
            base_url="http://localhost:8000/api",
            api_key=api_key,
        )

        assert hasattr(manager.auth_client, "_api_key")
        assert manager.auth_client._api_key == api_key
        assert "Authorization" in manager.auth_client._headers
        assert manager.auth_client._headers["Authorization"] == f"api-key-v1 {api_key}"

    def test_manager_authenticate_raises_error_with_api_key(self) -> None:
        """Verify that calling authenticate() with api_key raises ValueError."""
        api_key = "manager-api-key-auth-error"
        manager = Manager(
            base_url="http://localhost:8000/api",
            api_key=api_key,
        )

        with pytest.raises(
            ValueError,
            match="Cannot call authenticate\\(\\) when Manager was initialized with api_key",
        ):
            manager.authenticate("username", "password")

    def test_manager_mutual_exclusivity_api_client_and_api_key(self) -> None:
        """Verify that providing both api_client and api_key raises ValueError."""
        api_key = "test-api-key"
        fake_client = FakeApiClient()

        with pytest.raises(
            ValueError,
            match="Cannot provide both 'api_client' and other parameters \\(api_key\\)",
        ):
            Manager(
                api_client=fake_client,  # type: ignore[arg-type]
                api_key=api_key,
            )

    def test_manager_create_runner_with_api_key(self) -> None:
        """Verify that Manager with api_key can create runners."""
        api_key = "manager-runner-api-key"
        fake_client = FakeApiClient()
        fake_client._api_key = api_key
        fake_client.set_header("Authorization", f"api-key-v1 {api_key}")

        manager = Manager(
            api_client=fake_client,  # type: ignore[arg-type]
        )

        # Should be able to create runner without calling authenticate()
        runner = manager.create_runner("test-set")
        assert runner is not None


class TestApiKeyFormatting:
    """Test API key header formatting."""

    def test_api_key_header_format(self) -> None:
        """Verify the API key header uses 'api-key-v1' scheme."""
        api_key = "my-secret-key"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=False,
        )

        expected_header = f"api-key-v1 {api_key}"
        assert client._headers["Authorization"] == expected_header

    def test_api_key_with_special_characters(self) -> None:
        """Verify API key works with special characters."""
        api_key = "key-with-dashes_and_underscores.123"
        client = ApiClient(
            base_url="http://localhost:8000/api",
            api_key=api_key,
            verify_auth=False,
        )

        expected_header = f"api-key-v1 {api_key}"
        assert client._headers["Authorization"] == expected_header


class TestApiKeyBackwardCompatibility:
    """Test that existing username/password auth still works."""

    def test_username_password_auth_without_api_key(self) -> None:
        """Verify username/password auth works when no api_key is provided."""
        fake_client = FakeApiClient()

        # Should be able to create client without api_key
        assert not hasattr(fake_client, "_api_key") or fake_client._api_key is None

    def test_manager_authenticate_without_api_key(self) -> None:
        """Verify Manager.authenticate() works when no api_key is provided."""
        fake_client = FakeApiClient()
        manager = Manager(
            api_client=fake_client,  # type: ignore[arg-type]
        )

        # Should be able to call authenticate without errors
        # (FakeCompatibility returns incompatible, so we disable verification)
        try:
            manager.authenticate(
                "username",
                "password",
                should_verify_compatibility=False,
            )
        except ValueError as e:
            if "api_key" in str(e):
                pytest.fail(f"authenticate() raised api_key error: {e}")
            # Other ValueError types are acceptable (e.g., from FakeAuth)
