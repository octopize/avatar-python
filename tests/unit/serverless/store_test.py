from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from avatars.models import JobKind, JobStatus
from avatars.serverless.store import JobRecord, ServerlessStore, SetRecord


def make_job(
    *,
    display_name: str = "run",
    set_name=None,
    kind: JobKind = JobKind.standard,
    parameters_name: str = "standard",
    created_at: datetime | None = None,
) -> JobRecord:
    return JobRecord(
        name=str(uuid4()),
        set_name=set_name or uuid4(),
        display_name=display_name,
        parameters_name=parameters_name,
        kind=kind,
        created_at=created_at or datetime.now(UTC),
    )


class TestPersistence:
    def test_a_fresh_store_survives_a_restart(self, tmp_path: Path) -> None:
        """The reason the store is on disk: three Manager methods look up by name
        from a client built after a kernel restart.
        """
        index = tmp_path / "index.json"
        job = make_job(display_name="my_dataset")
        ServerlessStore(index).add_job(job)

        reopened = ServerlessStore(index)
        assert reopened.get_job(job.name) is not None
        assert reopened.find_jobs(display_name="my_dataset")[0].name == job.name

    def test_missing_index_is_an_empty_store_not_an_error(self, tmp_path: Path) -> None:
        assert ServerlessStore(tmp_path / "nope.json").find_jobs() == []

    def test_write_is_atomic_leaving_no_temp_files(self, tmp_path: Path) -> None:
        index = tmp_path / "index.json"
        store = ServerlessStore(index)
        store.add_job(make_job())
        assert [p.name for p in tmp_path.iterdir()] == ["index.json"]


class TestSeedingSalt:
    def test_the_salt_is_minted_once_and_then_reused(self, tmp_path: Path) -> None:
        """A salt that changed per kernel restart would make the same seed produce
        different avatars, which is the one thing reproducibility must not do.
        """
        index = tmp_path / "index.json"
        first = ServerlessStore(index).seeding_salt(default=1234)
        assert first == 1234
        assert ServerlessStore(index).seeding_salt(default=9999) == 1234


class TestFiltering:
    def test_newest_first(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        now = datetime.now(UTC)
        old = store.add_job(make_job(created_at=now - timedelta(hours=1)))
        new = store.add_job(make_job(created_at=now))
        assert [j.name for j in store.find_jobs()] == [new.name, old.name]

    def test_limit_applies_after_sorting(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        now = datetime.now(UTC)
        store.add_job(make_job(created_at=now - timedelta(hours=1)))
        newest = store.add_job(make_job(created_at=now))
        assert [j.name for j in store.find_jobs(limit=1)] == [newest.name]

    def test_filter_by_kind(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        store.add_job(make_job(kind=JobKind.standard))
        metrics = store.add_job(make_job(kind=JobKind.privacy_metrics))
        found = store.find_jobs(kind=[JobKind.privacy_metrics])
        assert [j.name for j in found] == [metrics.name]

    def test_filter_by_set(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        wanted = uuid4()
        mine = store.add_job(make_job(set_name=wanted))
        store.add_job(make_job())
        assert [j.name for j in store.find_jobs(set_name=wanted)] == [mine.name]

    def test_display_name_and_set_name_are_mutually_exclusive(self, tmp_path: Path) -> None:
        """Matches the server, and the existing FakeJobs double."""
        store = ServerlessStore(tmp_path / "i.json")
        with pytest.raises(ValueError, match="mutually exclusive"):
            store.find_jobs(display_name="a", set_name=uuid4())


class TestDeletion:
    def test_soft_delete_hides_by_default_and_is_recoverable(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        job = store.add_job(make_job())
        assert store.soft_delete(job.name) is True
        assert store.find_jobs() == []
        assert [j.name for j in store.find_jobs(include_deleted=True)] == [job.name]

    def test_deleting_twice_reports_the_second_as_a_miss(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        job = store.add_job(make_job())
        assert store.soft_delete(job.name) is True
        assert store.soft_delete(job.name) is False

    def test_deleting_an_unknown_job_is_a_miss_not_an_error(self, tmp_path: Path) -> None:
        assert ServerlessStore(tmp_path / "i.json").soft_delete("nope") is False


class TestLastSet:
    def test_returns_every_job_of_the_most_recent_set_only(self, tmp_path: Path) -> None:
        store = ServerlessStore(tmp_path / "i.json")
        now = datetime.now(UTC)
        old_set, new_set = uuid4(), uuid4()
        store.add_job(make_job(set_name=old_set, created_at=now - timedelta(hours=2)))
        store.add_job(make_job(set_name=new_set, created_at=now - timedelta(minutes=1)))
        store.add_job(make_job(set_name=new_set, created_at=now))
        assert {j.set_name for j in store.last_set_jobs()} == {new_set}
        assert len(store.last_set_jobs()) == 2

    def test_empty_store(self, tmp_path: Path) -> None:
        assert ServerlessStore(tmp_path / "i.json").last_set_jobs() == []


class TestJobResponseConversion:
    def test_carries_every_field_the_sdk_reads(self, tmp_path: Path) -> None:
        job = make_job(display_name="d", parameters_name="standard")
        job.status = JobStatus.finished
        job.done = True
        job.progress = 1.0
        response = job.to_response()
        assert response.name == job.name
        assert response.display_name == "d"
        assert response.parameters_name == "standard"
        assert response.status == JobStatus.finished
        assert response.done is True
        assert response.progress == 1.0


class TestSets:
    def test_round_trip(self, tmp_path: Path) -> None:
        index = tmp_path / "i.json"
        record = SetRecord(set_name=uuid4(), display_name="my_dataset")
        ServerlessStore(index).add_set(record)
        reloaded = ServerlessStore(index).get_set(record.set_name)
        assert reloaded is not None
        assert reloaded.display_name == "my_dataset"

    def test_unknown_set_is_none(self, tmp_path: Path) -> None:
        assert ServerlessStore(tmp_path / "i.json").get_set(uuid4()) is None


def test_an_index_from_a_newer_sdk_is_refused(tmp_path: Path) -> None:
    """Rewriting it in this SDK's layout could lose what the newer one recorded."""
    index = tmp_path / "index.json"
    index.write_text('{"version": 99, "jobs": {}, "sets": {}}')
    with pytest.raises(ValueError, match="newer version of the SDK"):
        ServerlessStore(index)
