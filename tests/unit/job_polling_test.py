from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from avatars.constants import (
    MAX_POLL_INTERVAL_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    POLL_INTERVAL_FACTOR,
)
from avatars.job_polling import next_poll_wait, wait_for_jobs
from avatars.models import JobKind, JobResponse, JobStatus
from tests.unit.conftest import create_fake_job

SERVER_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds

    @property
    def elapsed(self) -> float:
        return self.current


class FakeJobApi:
    """Fake API where each job becomes done at a given time on the fake clock."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.started_at: dict[str, float] = {}
        self.created_at: dict[str, datetime] = {}
        self.done_at: dict[str, float] = {}
        self.final_status: dict[str, JobStatus] = {}
        self.exceptions: dict[str, str] = {}
        self.checks: dict[str, list[float]] = {}

    def add_job(
        self,
        name: str,
        *,
        age: float | None = None,
        server_created_at: datetime = SERVER_TIME,
        done_at: float,
        final_status: JobStatus = JobStatus.finished,
        exception: str = "",
    ) -> None:
        if age is not None:
            self.started_at[name] = -age
        self.created_at[name] = server_created_at
        self.done_at[name] = done_at
        self.final_status[name] = final_status
        self.exceptions[name] = exception
        self.checks[name] = []

    def fetch(self, name: str) -> JobResponse:
        elapsed = self.clock.elapsed
        self.checks[name].append(elapsed)
        is_done = elapsed >= self.done_at[name]
        return create_fake_job(
            name=name,
            kind=JobKind.standard,
            status=self.final_status[name] if is_done else JobStatus.pending,
            created_at=self.created_at[name],
            done=is_done,
            exception=self.exceptions[name] if is_done else "",
        )


class TestNextPollWait:
    def test_zero_elapsed_gives_minimum(self):
        assert next_poll_wait(0) == MIN_POLL_INTERVAL_SECONDS

    def test_negative_elapsed_gives_minimum(self):
        assert next_poll_wait(-30) == MIN_POLL_INTERVAL_SECONDS

    def test_small_elapsed_gives_minimum(self):
        assert next_poll_wait(1) == MIN_POLL_INTERVAL_SECONDS

    def test_minimum_ends_where_factor_reaches_minimum(self):
        boundary = MIN_POLL_INTERVAL_SECONDS / POLL_INTERVAL_FACTOR
        assert next_poll_wait(boundary) == pytest.approx(MIN_POLL_INTERVAL_SECONDS)
        assert next_poll_wait(boundary + 1) > MIN_POLL_INTERVAL_SECONDS

    def test_seven_seconds_gives_about_one_second(self):
        assert next_poll_wait(7) == pytest.approx(1.05)

    def test_about_33_seconds_gives_about_five_seconds(self):
        assert next_poll_wait(33) == pytest.approx(4.95)

    def test_cap_is_reached_at_about_two_minutes(self):
        boundary = MAX_POLL_INTERVAL_SECONDS / POLL_INTERVAL_FACTOR
        assert next_poll_wait(boundary - 1) < MAX_POLL_INTERVAL_SECONDS
        assert next_poll_wait(boundary) == pytest.approx(MAX_POLL_INTERVAL_SECONDS)
        assert 120 < boundary < 140

    @pytest.mark.parametrize("elapsed", [200, 3600, 10**9])
    def test_never_exceeds_maximum(self, elapsed: float):
        assert next_poll_wait(elapsed) == MAX_POLL_INTERVAL_SECONDS

    def test_is_non_decreasing(self):
        waits = [next_poll_wait(t) for t in range(0, 400, 5)]
        assert waits == sorted(waits)


class TestWaitForJobs:
    def setup_method(self):
        self.clock = FakeClock()
        self.api = FakeJobApi(self.clock)

    def test_job_done_at_first_check_does_not_sleep(self):
        self.api.add_job("a", done_at=0)

        result = wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

        assert result["a"].done
        assert self.clock.sleeps == []
        assert self.api.checks["a"] == [0]

    def test_short_job_is_seen_within_one_minimum_interval(self):
        self.api.add_job("a", done_at=0.1)

        wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

        assert self.api.checks["a"] == [0, MIN_POLL_INTERVAL_SECONDS]
        assert self.clock.elapsed - 0.1 <= MIN_POLL_INTERVAL_SECONDS

    def test_new_job_is_checked_at_the_minimum_rate(self):
        self.api.add_job("a", done_at=1.0)

        wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

        assert self.api.checks["a"] == pytest.approx([0, 0.25, 0.5, 0.75, 1.0])

    def test_interval_grows_with_the_age_of_the_job(self):
        self.api.add_job("a", done_at=60)

        wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

        gaps = [b - a for a, b in pairwise(self.api.checks["a"])]
        assert gaps == sorted(gaps)
        assert gaps[0] == MIN_POLL_INTERVAL_SECONDS
        assert gaps[-1] > 5

    @pytest.mark.parametrize(
        "server_created_at",
        [
            SERVER_TIME - timedelta(hours=3),
            SERVER_TIME + timedelta(hours=3),
            SERVER_TIME - timedelta(days=400),
        ],
    )
    def test_server_created_at_does_not_change_the_schedule(self, server_created_at: datetime):
        self.api.add_job("a", age=0, server_created_at=server_created_at, done_at=1.0)

        wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

        assert self.api.checks["a"] == pytest.approx([0, 0.25, 0.5, 0.75, 1.0])

    def test_job_without_known_start_starts_at_its_first_check(self):
        self.clock.current = 500.0
        self.api.add_job("a", done_at=501.0)

        wait_for_jobs(["a"], self.api.fetch, self.clock)

        assert self.api.checks["a"] == pytest.approx([500, 500.25, 500.5, 500.75, 501.0])

    def test_old_job_keeps_the_maximum_interval(self):
        self.api.add_job("a", age=3600, done_at=60)

        wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

        assert self.api.checks["a"] == pytest.approx([0, 20, 40, 60])

    def test_new_job_is_checked_fast_while_old_job_is_checked_slowly(self):
        self.api.add_job("old", age=3600, done_at=60)
        self.api.add_job("new", done_at=3)

        result = wait_for_jobs(["old", "new"], self.api.fetch, self.clock, self.api.started_at)

        assert set(result) == {"old", "new"}
        assert self.api.checks["old"] == pytest.approx([0, 20, 40, 60])
        new_checks = self.api.checks["new"]
        assert new_checks[:6] == pytest.approx([0, 0.25, 0.5, 0.75, 1.0, 1.25])
        assert 3.0 <= new_checks[-1] <= 3.0 + next_poll_wait(3.0)
        assert len([t for t in new_checks if t < 20]) == len(new_checks)

    def test_checks_a_job_added_later_in_the_list_without_waiting_for_the_first(self):
        self.api.add_job("slow", done_at=100)
        self.api.add_job("fast", done_at=0.5)

        wait_for_jobs(["slow", "fast"], self.api.fetch, self.clock, self.api.started_at)

        assert self.api.checks["fast"][-1] == pytest.approx(0.5)

    def test_returns_after_the_last_job_is_done(self):
        self.api.add_job("a", done_at=2)
        self.api.add_job("b", done_at=5)

        wait_for_jobs(["a", "b"], self.api.fetch, self.clock, self.api.started_at)

        assert 2 <= self.api.checks["a"][-1] <= 2 + next_poll_wait(2)
        assert 5 <= self.api.checks["b"][-1] <= 5 + next_poll_wait(5)
        assert self.clock.elapsed == self.api.checks["b"][-1]

    def test_duplicate_names_are_checked_once_per_round(self):
        self.api.add_job("a", done_at=0)

        wait_for_jobs(["a", "a"], self.api.fetch, self.clock, self.api.started_at)

        assert self.api.checks["a"] == [0]

    def test_no_jobs_returns_at_once(self):
        assert wait_for_jobs([], self.api.fetch, self.clock, self.api.started_at) == {}
        assert self.clock.sleeps == []

    @pytest.mark.parametrize(
        "status",
        [JobStatus.error, JobStatus.parent_error, JobStatus.lost, JobStatus.orphaned],
    )
    def test_error_status_with_exception_raises_value_error(self, status: JobStatus):
        self.api.add_job("a", done_at=0, final_status=status, exception="boom")

        with pytest.raises(ValueError, match="Job a failed with exception: boom"):
            wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

    def test_error_status_without_exception_raises_internal_error(self):
        self.api.add_job("a", done_at=0, final_status=JobStatus.error)

        with pytest.raises(ValueError, match="internal error"):
            wait_for_jobs(["a"], self.api.fetch, self.clock, self.api.started_at)

    def test_error_is_raised_when_seen_and_stops_the_wait(self):
        self.api.add_job("ok", age=3600, done_at=1000)
        self.api.add_job("bad", done_at=1, final_status=JobStatus.error, exception="boom")

        with pytest.raises(ValueError, match="Job bad failed"):
            wait_for_jobs(["ok", "bad"], self.api.fetch, self.clock, self.api.started_at)

        assert self.clock.elapsed == pytest.approx(1)

    def test_first_failed_job_in_the_list_is_raised_first(self):
        self.api.add_job("a", done_at=0, final_status=JobStatus.error, exception="first")
        self.api.add_job("b", done_at=0, final_status=JobStatus.error, exception="second")

        with pytest.raises(ValueError, match="Job a failed with exception: first"):
            wait_for_jobs(["a", "b"], self.api.fetch, self.clock, self.api.started_at)

    def test_fetch_errors_are_not_caught(self):
        calls: list[str] = []

        def fetch(name: str) -> JobResponse:
            calls.append(name)
            raise ConnectionError("network down")

        with pytest.raises(ConnectionError, match="network down"):
            wait_for_jobs(["a"], fetch, self.clock)

        assert calls == ["a"]
        assert self.clock.sleeps == []

    def test_fetch_error_after_some_polls_is_raised_without_more_sleep(self):
        self.api.add_job("a", done_at=100)
        real_fetch = self.api.fetch

        def fetch(name: str) -> JobResponse:
            if self.clock.elapsed >= 0.5:
                raise TimeoutError("timeout")
            return real_fetch(name)

        with pytest.raises(TimeoutError):
            wait_for_jobs(["a"], fetch, self.clock)

        assert self.clock.elapsed == pytest.approx(0.5)
