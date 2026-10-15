import pytest

from avatars.constants import aggregate_job_status
from avatars.models import JobStatus


class TestAggregateJobStatus:
    """Unit tests for the aggregate_job_status function.

    Priority: failure > cancelled > pending/created > queued/default > finished
    """

    @pytest.mark.parametrize(
        ("statuses", "expected"),
        [
            # All finished
            ([JobStatus.finished], JobStatus.finished),
            # Empty list
            ([], JobStatus.finished),
            # Pending beats finished
            ([JobStatus.pending, JobStatus.finished], JobStatus.pending),
            # Created beats finished (created is pending-like)
            ([JobStatus.created, JobStatus.finished], JobStatus.created),
            # Queued beats finished
            ([JobStatus.queued, JobStatus.finished], JobStatus.queued),
            # Default beats finished (default is queued-like)
            ([JobStatus.field_, JobStatus.finished], JobStatus.field_),
            # Error beats pending
            ([JobStatus.error, JobStatus.pending], JobStatus.error),
            # Parent error beats pending
            ([JobStatus.parent_error, JobStatus.pending], JobStatus.parent_error),
            # Lost beats pending
            ([JobStatus.lost, JobStatus.pending], JobStatus.lost),
            # Orphaned beats pending
            ([JobStatus.orphaned, JobStatus.pending], JobStatus.orphaned),
            # Error beats queued
            ([JobStatus.error, JobStatus.queued], JobStatus.error),
            # Pending beats queued
            ([JobStatus.pending, JobStatus.queued], JobStatus.pending),
            # A failure beats a cancel: it is the news
            ([JobStatus.cancelled, JobStatus.error], JobStatus.error),
            # A cancel beats anything still running: the run will not deliver
            ([JobStatus.pending, JobStatus.cancelled], JobStatus.cancelled),
            ([JobStatus.cancelled, JobStatus.finished], JobStatus.cancelled),
            # First failure status wins when multiple failures
            (
                [JobStatus.error, JobStatus.parent_error],
                JobStatus.error,
            ),
        ],
    )
    def test_returns_worst_status(self, statuses: list[JobStatus], expected: JobStatus) -> None:
        assert aggregate_job_status(statuses) == expected


def test_a_cancelled_job_is_ready() -> None:
    """Over, so a wait on it ends -- and not an error, because nothing failed."""
    from avatars.constants import ERROR_STATUSES, READY_STATUSES  # noqa: PLC0415

    assert JobStatus.cancelled in READY_STATUSES
    assert JobStatus.cancelled not in ERROR_STATUSES
