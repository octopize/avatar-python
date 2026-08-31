"""Unit tests for API key authentication."""

import os
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import httpx
import pytest

from avatars.base_client import ApiConnectionError, ContextData
from avatars.client import ApiClient
from avatars.manager import Manager
from tests.unit.conftest import FakeApiClient, FakeIncompatibleCompatibility


def make_manager(**kwargs: Any) -> Manager:
    """Create a Manager with default test settings."""
    return Manager(**kwargs)


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
        fake_client = FakeApiClient()
        fake_client.set_api_key(api_key)

        manager = make_manager(
            api_client=fake_client,
        )

        assert hasattr(manager.auth_client, "_api_key")
        assert manager.auth_client._api_key == api_key
        assert "Authorization" in manager.auth_client._headers
        assert manager.auth_client._headers["Authorization"] == f"api-key-v1 {api_key}"

    def test_manager_mutual_exclusivity_api_client_and_api_key(self) -> None:
        """Verify that providing both api_client and api_key raises ValueError."""
        api_key = "test-api-key"
        fake_client = FakeApiClient()

        with pytest.raises(
            ValueError,
            match="Cannot provide both 'api_client' and other parameters \\(api_key\\)",
        ):
            Manager(
                api_client=fake_client,
                api_key=api_key,
            )

    def test_manager_create_runner_with_api_key(self) -> None:
        """Verify that Manager with api_key can create runners."""
        api_key = "manager-runner-api-key"
        fake_client = FakeApiClient()
        fake_client.set_api_key(api_key)

        manager = make_manager(
            api_client=fake_client,
        )

        # Should be able to create runner without calling authenticate()
        runner = manager.create_runner("test-set")
        assert runner is not None

    def test_manager_with_api_key_checks_compatibility(self) -> None:
        """Verify that Manager with api_key checks compatibility and raises when incompatible."""
        api_key = "manager-runner-api-key"
        fake_client = FakeApiClient()
        fake_client.set_api_key(api_key)
        fake_client.compatibility = FakeIncompatibleCompatibility()  # type: ignore

        with pytest.raises(
            DeprecationWarning,
            match="Client is not compatible with the server.",
        ):
            Manager(
                api_client=fake_client,
            )

    def test_manager_without_api_key_raises(self) -> None:
        """Verify that Manager raises ValueError when no API key is configured."""
        with mock.patch.dict(os.environ, clear=True):
            with pytest.raises(ValueError, match="An API key is required"):
                Manager()


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


class TestManagerConnectionVerification:
    """Test that Manager verifies connection at creation time for API key auth."""

    def test_wrong_api_key_raises_connection_error_at_init(self) -> None:
        """Verify that a wrong API key raises ConnectionError at Manager creation."""
        fake_client = FakeApiClient()
        fake_client.set_api_key("wrong-api-key")
        # Make get_me raise an auth error like the real API would
        fake_client.users = MagicMock()
        fake_client.users.get_me.side_effect = Exception(
            "Got error in HTTP request: GET /users/me. Error status 401 - Not authenticated"
        )

        with pytest.raises(ApiConnectionError, match="verify your API key"):
            Manager(
                api_client=fake_client,
                should_verify_compatibility=False,
            )

    def test_unreachable_server_raises_connection_error_at_init(self) -> None:
        """Verify that an unreachable server raises ConnectionError at Manager creation."""
        fake_client = FakeApiClient()
        fake_client.set_api_key("some-api-key")
        fake_client.users = MagicMock()
        fake_client.users.get_me.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(ApiConnectionError, match="verify your base URL"):
            Manager(
                api_client=fake_client,
                should_verify_compatibility=False,
            )

    def test_valid_api_key_does_not_raise(self) -> None:
        """Verify that a valid API key does not raise any error."""
        fake_client = FakeApiClient()
        fake_client.set_api_key("valid-api-key")
        # FakeUsers.get_me() returns successfully by default

        manager = Manager(
            api_client=fake_client,
            should_verify_compatibility=False,
        )
        assert manager.auth_client is fake_client

    def test_generic_error_wraps_in_connection_error(self) -> None:
        """Verify that unexpected errors are wrapped in ConnectionError."""
        fake_client = FakeApiClient()
        fake_client.set_api_key("some-api-key")
        fake_client.users = MagicMock()
        fake_client.users.get_me.side_effect = Exception("Something unexpected happened")

        with pytest.raises(ApiConnectionError, match="Failed to connect to the Avatar API"):
            Manager(
                api_client=fake_client,
                should_verify_compatibility=False,
            )
