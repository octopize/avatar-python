"""Adaptive polling of job status.

Each job has its own check schedule. The wait before the next check of a job is a
fraction of the time since the job was created, kept between a minimum and a maximum.
"""

import time
from collections.abc import Callable, Iterable, Mapping
from typing import Protocol

from avatars.constants import (
    CANCELLED_STATUSES,
    ERROR_STATUSES,
    MAX_POLL_INTERVAL_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    POLL_INTERVAL_FACTOR,
)
from avatars.models import JobResponse


class Clock(Protocol):
    """Source of time and sleep for the polling loop."""

    def monotonic(self) -> float:
        """Return a monotonic time in seconds."""
        ...

    def sleep(self, seconds: float) -> None:
        """Block for the given number of seconds."""
        ...


class SystemClock:
    """Clock that uses the real time and really sleeps."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


SYSTEM_CLOCK: Clock = SystemClock()


def next_poll_wait(elapsed_seconds: float) -> float:
    """Compute the wait before the next status check of a job.

    Parameters
    ----------
    elapsed_seconds
        Time in seconds since the job started. A negative value counts as zero.

    Returns
    -------
    float
        ``POLL_INTERVAL_FACTOR * elapsed_seconds``, kept between
        ``MIN_POLL_INTERVAL_SECONDS`` and ``MAX_POLL_INTERVAL_SECONDS``.

    """
    wait = POLL_INTERVAL_FACTOR * elapsed_seconds
    return min(MAX_POLL_INTERVAL_SECONDS, max(MIN_POLL_INTERVAL_SECONDS, wait))


def wait_for_jobs(
    job_names: Iterable[str],
    fetch_job: Callable[[str], JobResponse],
    clock: Clock = SYSTEM_CLOCK,
    started_at: Mapping[str, float] | None = None,
) -> dict[str, JobResponse]:
    """Wait until all given jobs are done.

    The function keeps one next-check time for each job and sleeps until the earliest
    one. A job that runs for a long time does not delay the checks of a new job.

    Parameters
    ----------
    job_names
        Names of the jobs to wait for. A name that appears more than once counts once.
    fetch_job
        Function that returns the current :class:`~avatars.models.JobResponse` of a job.
    clock
        Source of time and sleep.
    started_at
        Start time of each job on the clock, in the unit of ``clock.monotonic()``.
        A job that is not in the mapping starts when the first check of it begins.

    Returns
    -------
    dict[str, JobResponse]
        The last response of each job, when the job is done.

    Raises
    ------
    ValueError
        If a job has an error status. Other errors of ``fetch_job`` are not caught.

    """
    pending = list(dict.fromkeys(job_names))
    first_check = clock.monotonic()
    starts = {name: (started_at or {}).get(name, first_check) for name in pending}
    due_at = dict.fromkeys(pending, first_check)
    finished: dict[str, JobResponse] = {}

    while pending:
        now = clock.monotonic()
        earliest = min(due_at[name] for name in pending)
        if earliest > now:
            clock.sleep(earliest - now)
            now = clock.monotonic()

        for name in list(pending):
            if due_at[name] > now:
                continue
            job = fetch_job(name)
            _raise_if_failed(name, job)
            if job.done:
                finished[name] = job
                pending.remove(name)
                continue
            checked_at = clock.monotonic()
            due_at[name] = checked_at + next_poll_wait(checked_at - starts[name])

    return finished


def _raise_if_failed(job_name: str, job: JobResponse) -> None:
    if job.status in ERROR_STATUSES:
        if job.exception:
            raise ValueError(f"Job {job_name} failed with exception: {job.exception}")
        raise ValueError("internal error")
    if job.status in CANCELLED_STATUSES:
        # Over, with nothing to fetch: waiting on would never end, and asking for
        # results would fail on files that were never written.
        raise ValueError(f"Job {job_name} was cancelled: {job.exception}")
