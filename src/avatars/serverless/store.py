"""The jobs and sets a serverless workdir remembers.

On the server these are Postgres rows. Here they are one JSON file, because three
``Manager`` methods -- ``create_runner_from_name``, ``get_last_jobs`` and
``find_ids_by_name`` -- look up work by name *from a fresh client*. An in-memory
store would make them silently return nothing after a kernel restart, which in a
notebook is the normal case rather than the exceptional one.

The file is rewritten whole under ``os.replace``, so a crash mid-write leaves the
previous index intact rather than a truncated one.
"""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from avatars.models import JobKind, JobResponse, JobStatus


class JobRecord(BaseModel):
    """One job, carrying everything ``JobResponse`` needs plus what we need to run it."""

    name: str
    set_name: UUID
    display_name: str
    parameters_name: str
    kind: JobKind
    status: JobStatus = JobStatus.created
    exception: str = ""
    done: bool = False
    progress: float | None = None
    phase: str | None = ""
    phase_done: int | None = 0
    phase_total: int | None = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = None
    # Job names (not parameters names): the Locations the SDK passed in `depends_on`,
    # resolved to the jobs they point at. The executor walks these to rebuild the
    # parameters hierarchy the engine's `create_dependent_config` wants.
    depends_on: list[str] = Field(default_factory=list)
    # The `jti` of the licence the job ran under, so that a result can be traced back
    # to the licence, and through the issuance ledger to the customer.
    license_jti: str | None = None

    def to_response(self) -> JobResponse:
        return JobResponse(
            name=self.name,
            set_name=self.set_name,
            parameters_name=self.parameters_name,
            display_name=self.display_name,
            created_at=self.created_at,
            kind=self.kind,
            status=self.status,
            exception=self.exception,
            done=self.done,
            progress=self.progress,
            phase=self.phase,
            phase_done=self.phase_done,
            phase_total=self.phase_total,
        )


class SetRecord(BaseModel):
    """One resource set: the YAML a ``Runner`` uploaded, and the name it goes by."""

    set_name: UUID
    display_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


INDEX_VERSION = 1


class _Index(BaseModel):
    version: int = INDEX_VERSION
    jobs: dict[str, JobRecord] = Field(default_factory=dict)
    sets: dict[str, SetRecord] = Field(default_factory=dict)
    # Kept here rather than regenerated per process: on the server this is the user's
    # `reproducibility_salt`, a constant. A salt that changed every kernel restart
    # would make the same `seed` produce different avatars, which is the one thing
    # reproducibility must not do.
    seeding_salt: int | None = None


class ServerlessStore:
    """A JSON-file-backed stand-in for the API's job and resource tables."""

    def __init__(self, index_path: Path) -> None:
        self._path = index_path
        self._index = self._load()

    # -- persistence ---------------------------------------------------------------

    def _load(self) -> _Index:
        if not self._path.exists():
            return _Index()
        index = _Index.model_validate_json(self._path.read_text())
        # An index written by a newer SDK may mean something this one cannot read
        # right; refusing is safer than rewriting it in the old layout.
        if index.version > INDEX_VERSION:
            raise ValueError(
                f"{self._path} was written by a newer version of the SDK (index version "
                f"{index.version}, this SDK reads {INDEX_VERSION}). Upgrade the SDK, or "
                "use another workdir."
            )
        return index

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: `os.replace` is atomic on POSIX and Windows alike, so a
        # crash here cannot leave a half-written index behind.
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(self._index.model_dump_json(indent=2))
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # -- seeding salt ----------------------------------------------------------------

    def seeding_salt(self, default: int) -> int:
        """The workdir's salt, minting and persisting one on first use."""
        if self._index.seeding_salt is None:
            self._index.seeding_salt = default
            self._flush()
        return self._index.seeding_salt

    # -- sets ------------------------------------------------------------------------

    def add_set(self, record: SetRecord) -> SetRecord:
        self._index.sets[str(record.set_name)] = record
        self._flush()
        return record

    def get_set(self, set_name: str | UUID) -> SetRecord | None:
        return self._index.sets.get(str(set_name))

    # -- jobs ------------------------------------------------------------------------

    def add_job(self, record: JobRecord) -> JobRecord:
        self._index.jobs[record.name] = record
        self._flush()
        return record

    def get_job(self, job_name: str) -> JobRecord | None:
        return self._index.jobs.get(job_name)

    def update_job(self, record: JobRecord) -> JobRecord:
        self._index.jobs[record.name] = record
        self._flush()
        return record

    def soft_delete(self, job_name: str) -> bool:
        """Mark a job deleted. Returns whether there was one to delete."""
        record = self._index.jobs.get(job_name)
        if record is None or record.deleted_at is not None:
            return False
        record.deleted_at = datetime.now(UTC)
        self._flush()
        return True

    def find_jobs(
        self,
        *,
        kind: list[JobKind] | None = None,
        display_name: str | None = None,
        set_name: str | UUID | None = None,
        names: list[str] | None = None,
        limit: int | None = None,
        include_deleted: bool = False,
    ) -> list[JobRecord]:
        """Jobs matching the filters, newest first -- the same order ``/jobs`` uses."""
        if display_name is not None and set_name is not None:
            raise ValueError("display_name and set_name are mutually exclusive filters.")

        jobs = list(self._index.jobs.values())
        if not include_deleted:
            jobs = [j for j in jobs if j.deleted_at is None]
        if display_name is not None:
            jobs = [j for j in jobs if j.display_name == display_name]
        if set_name is not None:
            jobs = [j for j in jobs if str(j.set_name) == str(set_name)]
        if kind is not None:
            jobs = [j for j in jobs if j.kind in kind]
        if names is not None:
            wanted = set(names)
            jobs = [j for j in jobs if j.name in wanted]

        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit] if limit is not None else jobs

    def last_set_jobs(self) -> list[JobRecord]:
        """Every job of the most recently created set, which is what ``/jobs/last_set`` returns."""
        jobs = self.find_jobs()
        if not jobs:
            return []
        latest = max(jobs, key=lambda j: j.created_at).set_name
        return [j for j in jobs if j.set_name == latest]
