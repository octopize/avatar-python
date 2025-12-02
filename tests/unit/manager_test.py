import os
from unittest import mock

import pytest

from avatars.client import ApiClient
from avatars.client_config import ClientConfig
from avatars.config import Config
from avatars.manager import Manager, Runner
from avatars.models import JobResponseList
from tests.unit.conftest import (
    FakeApiClient,
    JobResponseFactory,
)

EXPECTED_KWARGS = ["get_jobs_returned_value"]


class TestManager:
    manager: Manager

    @classmethod
    def setup_class(cls):
        api_client = FakeApiClient()
        cls.manager = Manager(
            api_client=api_client,  # type: ignore[arg-type]
        )

    def test_get_last_job(self) -> None:
        api_client = FakeApiClient(
            get_jobs_returned_value=JobResponseList(jobs=JobResponseFactory.batch(2))
        )
        manager = Manager(
            api_client=api_client,  # type: ignore[arg-type]
        )
        results = manager.get_last_results(1)  # check the get result mock
        assert len(results) == 1

    def test_create_runner(self) -> None:
        runner = self.manager.create_runner("test")
        assert runner is not None
        assert isinstance(runner, Runner)

    @pytest.mark.parametrize(
        "incompatibility_status",
        [
            "incompatible",
            "unknown",
        ],
    )
    def test_should_verify_compatibility(self, incompatibility_status: str) -> None:
        """Verify that the client raises a DeprecationWarning when the server is incompatible"""
        with pytest.raises(DeprecationWarning, match="Client is not compatible with the server."):
            with pytest.warns(DeprecationWarning):
                self.manager.authenticate(
                    username="username",
                    password="password",
                    should_verify_compatibility=True,
                )

    def test_should_not_verify_compatibility(self) -> None:
        """Verify that the client does not raise when should_verify_compatibility is False"""
        try:
            self.manager.authenticate(
                username="username",
                password="password",
                should_verify_compatibility=False,
            )
        except DeprecationWarning:
            pytest.fail("DeprecationWarning was raised unexpectedly.")

    def test_verify_compatibility_uses_config_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify manager uses config default when should_verify_compatibility is not provided."""

        # Patch config in the manager module where it's imported
        test_config = Config(VERIFY_COMPATIBILITY=True)
        monkeypatch.setattr("avatars.manager.config", test_config)

        # When should_verify_compatibility is not provided, it should use config and raise
        with pytest.raises(DeprecationWarning, match="Client is not compatible with the server."):
            with pytest.warns(DeprecationWarning):
                self.manager.authenticate(
                    username="username",
                    password="password",
                )

    def test_verify_compatibility_uses_config_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify manager uses config value when set to False."""

        # Patch config in the manager module where it's imported
        test_config = Config(VERIFY_COMPATIBILITY=False)
        monkeypatch.setattr("avatars.manager.config", test_config)

        # When should_verify_compatibility is not provided and config is False, should not raise
        try:
            self.manager.authenticate(
                username="username",
                password="password",
            )
        except DeprecationWarning:
            pytest.fail(
                "DeprecationWarning was raised unexpectedly"
                " when config.VERIFY_COMPATIBILITY is False"
            )

    def test_verify_compatibility_parameter_overrides_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify should_verify_compatibility parameter overrides the config."""

        # Patch config in the manager module where it's imported
        test_config = Config(VERIFY_COMPATIBILITY=True)
        monkeypatch.setattr("avatars.manager.config", test_config)

        # Even though config is True, explicit False parameter should override
        try:
            self.manager.authenticate(
                username="username",
                password="password",
                should_verify_compatibility=False,
            )
        except DeprecationWarning:
            pytest.fail(
                "DeprecationWarning was raised unexpectedly when should_verify_compatibility=False"
            )


class TestManagerInitialization:
    """Tests for Manager config parameter validation."""

    @pytest.fixture
    def minimal_config(self) -> ClientConfig:
        """Provide a minimal ClientConfig for testing."""
        return ClientConfig(
            base_api_url="https://custom.octopize.app/api",
            storage_endpoint_url="https://custom.octopize.app/storage",
        )

    def test_can_create_with_config_only(self, minimal_config: ClientConfig) -> None:
        """Test that Manager can be created with only a ClientConfig object."""
        manager = Manager(config=minimal_config)
        assert manager.auth_client is not None
        assert manager.auth_client.base_url == "https://custom.octopize.app/api"
        assert (
            manager.auth_client.data_uploader.storage_endpoint_url
            == "https://custom.octopize.app/storage"
        )

    def test_can_create_with_base_url_only_deprecated(self) -> None:
        """Test that Manager can be created with only base_url which points to the API."""
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            manager = Manager(base_url="https://api.example.com/api")
            assert manager.auth_client is not None
            assert manager.auth_client.base_url == "https://api.example.com/api"
            assert (
                manager.auth_client.data_uploader.storage_endpoint_url
                == "https://api.example.com/storage"
            )

    def test_can_create_with_base_url_only(self) -> None:
        """Test that Manager can be created with only base_url which points to the server."""
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            manager = Manager(base_url="https://api.example.com")
            assert manager.auth_client is not None

            # Make sure api url is correctly constructed
            assert manager.auth_client.base_url == "https://api.example.com/api"

            # Make sure storage endpoint URL is correctly constructed
            assert (
                manager.auth_client.data_uploader.storage_endpoint_url
                == "https://api.example.com/storage"
            )

    def test_empty_constructor_uses_defaults(self) -> None:
        """Test that Manager() with no arguments uses default config values."""
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            manager = Manager()
            # Manager should create auth_client with default config values
            assert manager.auth_client is not None
            assert manager.auth_client.base_url == "https://www.octopize.app/api"

    def test_empty_constructor_uses_env_vars_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that Manager() uses AVATAR_BASE_URL env var if set."""
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            monkeypatch.setenv("AVATAR_BASE_URL", "https://env.example.com")
            manager = Manager()
            # Manager should create auth_client with config values from env vars
            assert manager.auth_client is not None
            assert manager.auth_client.base_url == "https://env.example.com/api"
            assert (
                manager.auth_client.data_uploader.storage_endpoint_url
                == "https://env.example.com/storage"
            )

    def test_empty_constructor_uses_env_vars_base_api_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that Manager() uses AVATAR_BASE_API_URL env var if set.

        This test also ensures that AVATAR_STORAGE_ENDPOINT_URL is NOT inferred
        """
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            monkeypatch.setenv("AVATAR_BASE_API_URL", "https://env.example.com/api")
            manager = Manager()
            assert manager.auth_client is not None

            # Verify that BASE_API_URL is set from env var
            assert manager.auth_client.base_url == "https://env.example.com/api"

            # but STORAGE_ENDPOINT_URL is not inferred from BASE_API_URL
            assert (
                manager.auth_client.data_uploader.storage_endpoint_url
                == "https://www.octopize.app/storage"
            )

    def test_empty_constructor_uses_env_vars_storage_endpoint_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that Manager() uses AVATAR_STORAGE_ENDPOINT_URL env var if set.

        This test also ensures that AVATAR_BASE_API_URL is NOT inferred
        """
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            monkeypatch.setenv("AVATAR_STORAGE_ENDPOINT_URL", "https://env.example.com/storage")
            manager = Manager()
            assert manager.auth_client is not None

            # Verify that BASE_API_URL is set from env var
            assert manager.auth_client.base_url == "https://www.octopize.app/api"

            # but STORAGE_ENDPOINT_URL is not inferred from BASE_API_URL
            assert (
                manager.auth_client.data_uploader.storage_endpoint_url
                == "https://env.example.com/storage"
            )

    def test_no_base_url_and_no_config_but_env_vars_raises_if_conflict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with mock.patch.dict(
            os.environ,
            clear=True,
        ):
            monkeypatch.setenv("AVATAR_BASE_API_URL", "https://env.example.com/api")
            monkeypatch.setenv("AVATAR_BASE_URL", "https://env.example.com")

            with pytest.raises(
                ValueError,
                match="Cannot set BASE_URL together with BASE_API_URL or STORAGE_ENDPOINT_URL",
            ):
                Manager()

    def test_config_with_base_url_raises_error(self, minimal_config: ClientConfig) -> None:
        """Test that using config with base_url raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Cannot provide both 'config' and other parameters \\(base_url\\)",
        ):
            Manager(config=minimal_config, base_url="https://other.com")

    def test_config_with_api_key_raises_error(self, minimal_config: ClientConfig) -> None:
        """Test that using config with api_key raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Cannot provide both 'config' and other parameters \\(api_key\\)",
        ):
            Manager(config=minimal_config, api_key="test-key")

    def test_config_with_api_client_raises_error(self, minimal_config: ClientConfig) -> None:
        """Test that using config with api_client raises ValueError."""
        api_client = ApiClient(
            base_url="https://other.com/api",
            verify_auth=False,
        )
        with pytest.raises(
            ValueError,
            match="Cannot provide both 'api_client' and other parameters \\(config\\)",
        ):
            Manager(config=minimal_config, api_client=api_client)
