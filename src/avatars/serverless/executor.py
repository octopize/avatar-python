"""What it takes to run one job, stated without importing the engine.

The split matters. ``EngineJobExecutor`` (in ``engine.py``) is the only module that
imports ``avatar``, and it is therefore the only module that cannot be tested or
type-checked without the ``serverless`` extra installed. Everything that involves a
*decision* -- which jobs run, in what order, what an engine failure should say to the
user -- lives here instead, where it is ordinary testable Python.

``map_engine_exception`` in particular is matched on the exception's class *name*
rather than on an imported class, so the whole error-reporting surface can be
exercised against synthetic exceptions in the normal unit-test run.
"""

import re
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from avatars.models import JobStatus


@dataclass(frozen=True)
class PlannedRun:
    """One job, resolved to everything the engine needs to execute it.

    ``parent_parameters``/``grandparent_parameters`` name *parameters documents*, not
    jobs, because that is what ``avatar.processing.dependency.create_dependent_config``
    takes. Resolving job names to parameters names is the caller's job -- it mirrors
    ``JobService._extract_parameters_hierarchy``.
    """

    job_name: str
    parameters_name: str
    yaml_path: Path
    results_url: str
    parent_parameters: list[str] = field(default_factory=list)
    grandparent_parameters: dict[str, str] = field(default_factory=dict)


class JobExecutor(Protocol):
    """Runs a job, or raises.

    Implementations must not swallow failures: the caller records the status, and it
    needs the exception to decide what to record. ``EngineJobExecutor`` is the real
    one; tests inject a fake that writes canned results.
    """

    def execute(self, run: PlannedRun) -> None: ...


# The engine's exceptions carry license-agnostic messages; the API rewrites some of
# them before the user sees them. Serverless has to produce the *same* strings,
# because `Runner._retrieve_job_result_urls` renders `job.exception` verbatim and
# every support answer and troubleshooting doc is written against the server's
# wording. Keyed by class name so this module needs no engine import.
#
# Mirrors services/api/src/api/domain/job_exception_handling.py -- change both together.
_LICENCE_CODE = re.compile(r"AVTR-LIC-\d{3}")
_SIZE_LIMIT_EXCEPTIONS = frozenset({"TooManyLinesError", "TooManyDimensionsError"})


def map_engine_exception(job_name: str, exc: BaseException) -> tuple[JobStatus, str]:
    """The status and user-facing message a failed job should record."""
    name = type(exc).__name__

    if name == "LicenseError":
        # Verbatim from api/service/job.py -- see the module note above -- plus the
        # stable AVTR-LIC code when there is one: a job stopped because the build or the
        # licence expired is not a feature the licence lacks, and support needs the code.
        message = (
            f"Error in job '{job_name}': Your license does not allow you to access these features."
        )
        code = _LICENCE_CODE.search(str(exc))
        return JobStatus.error, f"{message} ({code.group(0)})" if code else message

    if name in _SIZE_LIMIT_EXCEPTIONS:
        return JobStatus.error, (
            f"This dataset is too large for your current license. {exc} "
            "Upgrade your plan to process larger datasets."
        )

    if name == "CustomFileNotFoundError":
        return JobStatus.error, f"file {exc} not found, try to upload it first"

    if name == "CustomReportFileNotFoundError":
        return JobStatus.error, (
            "Could not access result files for the report input in folder"
            f"{Path(str(exc)).parent}. "
            "Please check your volume path or use depends_on."
        )

    if name == "MemoryError":
        # The server's equivalent is a Dask KilledWorker. In-process there is no
        # worker to kill, so the kernel raises MemoryError instead -- but the advice
        # is the same, minus the "contact support" (there is no cluster to resize).
        return JobStatus.error, (
            "The job ran out of memory. Your dataset is probably too large to "
            "avatarize in this process. Try a smaller table, or use a server "
            "deployment for datasets of this size."
        )

    return JobStatus.error, f"{name}: {exc}"


def write_traceback(log_path: Path, job_name: str, exc: BaseException) -> None:
    """Record the full traceback next to the workdir, and say nothing if we cannot.

    The user-facing message is deliberately short; the traceback is what someone
    debugging actually needs, and a compiled engine's traceback is the only thing
    that will point at the failing stage. Failing to write it must never turn a job
    failure into a *different* failure, hence the broad suppression.
    """
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"Job {job_name} failed with {type(exc).__name__}\n\n"
            + "".join(traceback.format_exception(exc))
        )
    except OSError:
        pass
