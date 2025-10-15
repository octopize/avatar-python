import pytest

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
            "http://localhost:8000",
            api_client=api_client,  # type: ignore[arg-type]
        )

    def test_get_last_job(self) -> None:
        api_client = FakeApiClient(
            get_jobs_returned_value=JobResponseList(jobs=JobResponseFactory.batch(2))
        )
        manager = Manager(
            "http://localhost:8000",
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
