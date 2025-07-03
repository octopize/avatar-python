from avatars.manager import Manager, Runner
from avatars.models import JobResponseList
from tests.unit.conftest import FakeApiClient, JobResponseFactory

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
