import os
from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest

from avatars.client import ApiClient
from avatars.client_config import ClientConfig
from avatars.config import Config
from avatars.manager import Manager, Runner, _increment_display_name_version
from avatars.models import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    JobCreateRequest,
    JobKind,
)
from tests.unit.conftest import (
    FakeApiClient,
    JobResponseFactory,
    create_fake_job,
)


class TestManager:
    manager: Manager

    @classmethod
    def setup_class(cls):
        api_client = FakeApiClient()
        cls.manager = Manager(
            api_client=api_client,  # type: ignore[arg-type]
        )

    def test_get_last_job(self) -> None:
        api_client = FakeApiClient()
        for job in JobResponseFactory.batch(2):
            api_client.jobs.add_job(job)
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
        """Verify no compatibility error is raised when the check is disabled."""
        with pytest.warns(
            DeprecationWarning, match="Username/password authentication is deprecated"
        ):
            self.manager.authenticate(
                username="username",
                password="password",
                should_verify_compatibility=False,
            )

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
        # a compatibility error — but should still warn about password auth deprecation.
        with pytest.warns(
            DeprecationWarning, match="Username/password authentication is deprecated"
        ):
            self.manager.authenticate(
                username="username",
                password="password",
            )

    def test_verify_compatibility_parameter_overrides_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify should_verify_compatibility parameter overrides the config."""

        # Patch config in the manager module where it's imported
        test_config = Config(VERIFY_COMPATIBILITY=True)
        monkeypatch.setattr("avatars.manager.config", test_config)

        # Even though config is True, explicit False parameter should override compatibility check.
        # The deprecation warning about username/password should still be emitted.
        with pytest.warns(
            DeprecationWarning, match="Username/password authentication is deprecated"
        ):
            self.manager.authenticate(
                username="username",
                password="password",
                should_verify_compatibility=False,
            )

    def test_authenticate_emits_deprecation_warning(self) -> None:
        """Successful authenticate() must emit a DeprecationWarning with migration instructions."""
        with pytest.warns(DeprecationWarning) as record:
            self.manager.authenticate(
                username="username",
                password="password",
                should_verify_compatibility=False,
            )

        messages = [str(w.message) for w in record]
        combined = "\n".join(messages)
        assert "Username/password authentication is deprecated" in combined
        assert "create_api_key" in combined
        assert "AVATAR_API_KEY" in combined
        assert "python.docs.octopize.io" in combined


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


class TestFindSetNamesByDisplayName:
    """Test suite for Manager.find_set_names_by_display_name functionality."""

    def test_returns_matching_set_names(self):
        """Test that matching set_names are returned."""
        set_name1 = uuid4()
        set_name2 = uuid4()
        now = datetime.now(UTC)

        jobs = [
            create_fake_job(
                name="job1",
                set_name=set_name1,
                created_at=now - timedelta(days=1),
                display_name="test_dataset",
            ),
            create_fake_job(
                name="job2",
                set_name=set_name2,
                created_at=now - timedelta(days=5),
                display_name="test_dataset",
            ),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        results = manager.find_ids_by_name("test_dataset")

        assert len(results) == 2
        assert results[0][0] == str(set_name1)  # Newest first
        assert results[1][0] == str(set_name2)

    def test_returns_empty_list_when_no_matches(self):
        """Test that empty list is returned when no display_name matches."""
        jobs = [
            create_fake_job(display_name="other_dataset"),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        results = manager.find_ids_by_name("test_dataset")

        assert results == []

    def test_case_sensitive_matching(self):
        """Test that display_name matching is case-sensitive."""
        jobs = [
            create_fake_job(display_name="Test_Dataset"),
            create_fake_job(display_name="test_dataset"),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        results = manager.find_ids_by_name("test_dataset")

        assert len(results) == 1
        assert results[0][1][0].display_name == "test_dataset"

    def test_excludes_advice_jobs(self):
        """Test that advice jobs are excluded from results."""
        set_name_standard = uuid4()
        set_name_advice = uuid4()

        jobs = [
            create_fake_job(
                name="standard",
                set_name=set_name_standard,
                kind=JobKind.standard,
                display_name="test_dataset",
            ),
            create_fake_job(
                name="advice",
                set_name=set_name_advice,
                kind=JobKind.advice,
                display_name="test_dataset",
            ),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        results = manager.find_ids_by_name("test_dataset")

        assert len(results) == 1
        assert results[0][0] == str(set_name_standard)

    def test_sorts_by_newest_first(self):
        """Test that results are sorted by creation time (newest first)."""
        now = datetime.now(UTC)
        set_name_oldest = uuid4()
        set_name_middle = uuid4()
        set_name_newest = uuid4()

        jobs = [
            create_fake_job(
                name="middle",
                set_name=set_name_middle,
                created_at=now - timedelta(days=5),
                display_name="test_dataset",
            ),
            create_fake_job(
                name="oldest",
                set_name=set_name_oldest,
                created_at=now - timedelta(days=10),
                display_name="test_dataset",
            ),
            create_fake_job(
                name="newest",
                set_name=set_name_newest,
                created_at=now - timedelta(days=1),
                display_name="test_dataset",
            ),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        results = manager.find_ids_by_name("test_dataset")

        assert len(results) == 3
        assert results[0][0] == str(set_name_newest)
        assert results[1][0] == str(set_name_middle)
        assert results[2][0] == str(set_name_oldest)

    def test_handles_multiple_jobs_same_set_name(self):
        """Test that multiple jobs with the same set_name are not deduplicated."""
        set_name = uuid4()
        now = datetime.now(UTC)

        jobs = [
            create_fake_job(
                name="standard",
                set_name=set_name,
                kind=JobKind.standard,
                created_at=now - timedelta(days=1),
                display_name="test_dataset",
            ),
            create_fake_job(
                name="privacy_metrics",
                set_name=set_name,
                kind=JobKind.privacy_metrics,
                created_at=now - timedelta(days=2),
                display_name="test_dataset",
            ),
            create_fake_job(
                name="signal_metrics",
                set_name=set_name,
                kind=JobKind.signal_metrics,
                created_at=now - timedelta(days=3),
                display_name="test_dataset",
            ),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        results = manager.find_ids_by_name("test_dataset")

        # Only one entry for the set_name should be returned
        assert len(results) == 1

    def test_integration_with_create_runner_from_id(self):
        """Test the workflow: find set_names -> load runner by id."""
        set_name = uuid4()
        job = create_fake_job(set_name=set_name, display_name="test_dataset")
        fake_client = FakeApiClient()
        fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        found_set_names = manager.find_ids_by_name("test_dataset")
        assert len(found_set_names) == 1

        runner = manager.create_runner_from_id(found_set_names[0][0])

        assert runner is not None
        assert runner.set_name == str(set_name)
        assert runner.display_name == "test_dataset-v1"


class TestCreateRunnerFromId:
    def test_accepts_uuid_string(self):
        """Test that a valid UUID string is accepted."""
        set_name = uuid4()
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_id(str(set_name))

        assert runner is not None
        assert runner.set_name == str(set_name)

    def test_accepts_uuid_object(self):
        """Test that a UUID object is accepted and converted to string."""
        set_name = uuid4()
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_id(set_name)

        assert runner is not None
        assert runner.set_name == str(set_name)

    def test_rejects_invalid_uuid_string(self):
        """Test that an invalid UUID string raises ValueError."""
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        with pytest.raises(ValueError, match="Invalid set_name format"):
            manager.create_runner_from_id("not-a-uuid")

    def test_rejects_none(self):
        """Test that None raises TypeError."""
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        with pytest.raises(TypeError, match="str or UUID"):
            manager.create_runner_from_id(None)  # type: ignore[arg-type]

    def test_populates_runner_state(self):
        """Test that runner.config, jobs.config, and jobs.set_name are set correctly."""
        set_name = uuid4()
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_id(str(set_name))

        assert runner.set_name == str(set_name)
        assert runner.jobs.set_name == str(set_name)
        assert runner.config is not None
        assert runner.jobs.config is not None

    def test_create_runner_from_id_increments_display_name(self):
        """Loading a runner via create_runner_from_id gives an incremented display name."""
        set_name = uuid4()
        job = create_fake_job(set_name=set_name, display_name="test_dataset")
        fake_client = FakeApiClient()
        fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_id(str(set_name))

        assert runner.display_name == "test_dataset-v1"


class TestCreateRunnerFromSetName:
    def test_raises_value_error_when_no_match(self):
        """Test that ValueError is raised when no jobs match the display name."""
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        with pytest.raises(ValueError, match="No jobs found for display name 'unknown'"):
            manager.create_runner_from_name("unknown")

    def test_returns_runner_for_single_match(self):
        """Test that a runner is returned when exactly one set_name matches."""
        set_name = uuid4()
        job = create_fake_job(set_name=set_name, display_name="my_dataset", kind=JobKind.standard)
        fake_client = FakeApiClient()
        fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_name("my_dataset")

        assert runner is not None
        assert runner.set_name == str(set_name)

    def test_picks_most_recent_when_multiple_set_names(self):
        """Test that the most recent set_name is selected when multiple match."""
        now = datetime.now(UTC)
        set_name_old = uuid4()
        set_name_new = uuid4()

        jobs = [
            create_fake_job(
                set_name=set_name_old,
                display_name="my_dataset",
                created_at=now - timedelta(days=5),
            ),
            create_fake_job(
                set_name=set_name_new,
                display_name="my_dataset",
                created_at=now - timedelta(days=1),
            ),
        ]
        fake_client = FakeApiClient()
        for job in jobs:
            fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_name("my_dataset")

        assert runner.set_name == str(set_name_new)

    def test_create_runner_from_name_increments_display_name(self):
        """Loading a runner via create_runner_from_name gives an incremented display name."""
        set_name = uuid4()
        job = create_fake_job(set_name=set_name, display_name="test_dataset")
        fake_client = FakeApiClient()
        fake_client.jobs.add_job(job)
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_name("test_dataset")

        assert runner.display_name == "test_dataset-v1"


class TestIncrementDisplayNameVersion:
    def test_appends_v1_when_no_version(self):
        assert _increment_display_name_version("my_dataset") == "my_dataset-v1"

    def test_increments_existing_version(self):
        assert _increment_display_name_version("my_dataset-v1") == "my_dataset-v2"

    def test_increments_multi_digit_version(self):
        assert _increment_display_name_version("my_dataset-v9") == "my_dataset-v10"

    def test_does_not_match_mid_string_version(self):
        """A -vN that is not at the end is not treated as a version."""
        assert _increment_display_name_version("my-v2-dataset") == "my-v2-dataset-v1"

    def test_create_runner_from_yaml_increments_display_name(self):
        """Loading a runner via create_runner_from_yaml gives an incremented display name."""
        fake_client = FakeApiClient()
        manager = Manager(api_client=fake_client)

        runner = manager.create_runner_from_yaml("fixtures/yaml_from_web.yaml", "iris")

        assert runner.display_name == "iris-v1"


class TestManagerDeleteJobs:
    """Tests for Manager.delete_job, Manager.delete_job_by_id and Manager.delete_jobs."""

    def setup_method(self) -> None:
        self.fake_api_client = FakeApiClient()
        self.manager = Manager(api_client=self.fake_api_client)  # type: ignore[arg-type]

    def test_delete_job_by_display_name(self) -> None:
        set_name = uuid4()
        job = create_fake_job(set_name=set_name, display_name="my_run", kind=JobKind.standard)
        self.fake_api_client.jobs.add_job(job)

        result = self.manager.delete_job("my_run")

        assert isinstance(result, BulkDeleteResponse)
        assert len(result.deleted_jobs) == 1
        assert result.deleted_jobs[0].name == job.name

    def test_delete_job_raises_when_no_match(self) -> None:
        with pytest.raises(ValueError, match="No jobs found for display name 'nonexistent'"):
            self.manager.delete_job("nonexistent")

    def test_delete_job_raises_when_multiple_sets(self) -> None:
        set_name1 = uuid4()
        set_name2 = uuid4()
        self.fake_api_client.jobs.add_job(
            create_fake_job(
                name="job-set1",
                set_name=set_name1,
                display_name="shared_name",
                kind=JobKind.standard,
            )
        )
        self.fake_api_client.jobs.add_job(
            create_fake_job(
                name="job-set2",
                set_name=set_name2,
                display_name="shared_name",
                kind=JobKind.standard,
            )
        )

        with pytest.raises(ValueError, match="Multiple runs found"):
            self.manager.delete_job("shared_name")

    def test_delete_job_raises_error_message_contains_setnames(self) -> None:
        set_name1 = uuid4()
        set_name2 = uuid4()
        self.fake_api_client.jobs.add_job(
            create_fake_job(
                name="job-a", set_name=set_name1, display_name="shared_name", kind=JobKind.standard
            )
        )
        self.fake_api_client.jobs.add_job(
            create_fake_job(
                name="job-b", set_name=set_name2, display_name="shared_name", kind=JobKind.standard
            )
        )

        with pytest.raises(ValueError) as exc_info:
            self.manager.delete_job("shared_name")

        msg = str(exc_info.value)
        assert str(set_name1) in msg or str(set_name2) in msg
        assert "delete_job_by_id" in msg

    def test_delete_job_by_id(self) -> None:
        set_name = uuid4()
        job1 = create_fake_job(
            name="job1", set_name=set_name, kind=JobKind.standard, display_name="run1"
        )
        job2 = create_fake_job(
            name="job2", set_name=set_name, kind=JobKind.privacy_metrics, display_name="run1"
        )
        self.fake_api_client.jobs.add_job(job1)
        self.fake_api_client.jobs.add_job(job2)

        result = self.manager.delete_job_by_id(set_name)

        assert isinstance(result, BulkDeleteResponse)
        assert len(result.deleted_jobs) == 2
        assert result.failed_jobs == []

    def test_delete_job_by_id_no_matching_jobs(self) -> None:
        result = self.manager.delete_job_by_id(uuid4())
        assert isinstance(result, BulkDeleteResponse)
        assert result.deleted_jobs == []
        assert result.failed_jobs == []

    def test_delete_jobs_single_batch(self) -> None:
        job_names = [
            self.fake_api_client.jobs.create_job(
                JobCreateRequest(set_name=uuid4(), parameters_name=f"params-{i}")
            ).name
            for i in range(50)
        ]
        result = self.manager.delete_jobs(job_names)
        assert isinstance(result, BulkDeleteResponse)
        assert len(result.deleted_jobs) == 50
        assert result.failed_jobs == []

    def test_delete_jobs_not_found(self) -> None:
        result = self.manager.delete_jobs(["nonexistent-1", "nonexistent-2"])
        assert isinstance(result, BulkDeleteResponse)
        assert result.deleted_jobs == []
        assert result.failed_jobs == ["nonexistent-1", "nonexistent-2"]

    def test_delete_jobs_multiple_batches(self) -> None:
        """Verify that >100 job names are split into multiple 100-job API calls."""
        job_names = [
            self.fake_api_client.jobs.create_job(
                JobCreateRequest(set_name=uuid4(), parameters_name=f"params-{i}")
            ).name
            for i in range(250)
        ]
        result = self.manager.delete_jobs(job_names)

        # Should have made 3 calls: 100 + 100 + 50
        calls = self.fake_api_client.jobs.bulk_delete_calls
        assert len(calls) == 3
        assert calls[0] == BulkDeleteRequest(job_names=job_names[:100])
        assert calls[1] == BulkDeleteRequest(job_names=job_names[100:200])
        assert calls[2] == BulkDeleteRequest(job_names=job_names[200:])
        assert len(result.deleted_jobs) == 250
        assert result.failed_jobs == []

    def test_delete_jobs_empty_list(self) -> None:
        result = self.manager.delete_jobs([])
        assert isinstance(result, BulkDeleteResponse)
        assert result.deleted_jobs == []
        assert result.failed_jobs == []
