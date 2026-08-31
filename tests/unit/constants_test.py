import pytest

from avatars.constants import aggregate_job_status
from avatars.models import JobStatus


class TestAggregateJobStatus:
    """Unit tests for the aggregate_job_status function.

    Priority: failure > pending/created > queued/default > finished
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
            # First failure status wins when multiple failures
            (
                [JobStatus.error, JobStatus.parent_error],
                JobStatus.error,
            ),
        ],
    )
    def test_returns_worst_status(self, statuses: list[JobStatus], expected: JobStatus) -> None:
        assert aggregate_job_status(statuses) == expected
