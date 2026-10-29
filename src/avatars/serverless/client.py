"""A client that runs the engine in this process instead of calling a server.

Satisfies :class:`avatars.sdk_client.SdkClient`, so ``Manager`` and ``Runner`` drive
it without knowing the difference. What it has to reproduce is small and precise --
twelve methods, one raw ``POST /jobs``, and the ``/access?url=`` envelope -- because
that is all the hand-written SDK ever asks of a client.

What it deliberately does *not* reproduce: API keys, event logs, capabilities, the
OpenAPI document, connection probes and document content-kind proposals. Those need
a server to mean anything, and a stub that silently returned something plausible
would be worse than one that says so. They raise :class:`NotAvailableOfflineError`.

Nothing here is secret, and nothing here decides anything about licensing: this file
is mirrored verbatim into the public ``octopize/avatar-python`` repository. The
licence is verified inside the compiled engine; this module only carries the answer
around and renders the error.
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pandas as pd
import yaml
from avatar_yaml.models.common import ModelKind
from structlog import get_logger

from avatars.input_files import InputFiles, input_files_listing
from avatars.models import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    CompatibilityResponse,
    CompatibilityStatus,
    EnvironmentInfo,
    FileAccess,
    FileCredentials,
    JobCreateRequest,
    JobCreateResponse,
    JobKind,
    JobResponse,
    JobResponseList,
    JobStatus,
    MeUser,
    ResourceSetResponse,
    UserRole,
)
from avatars.sdk_client import SdkClient
from avatars.serverless.access import SERVERLESS_BASE_URL, map_to_access_url, to_local_path
from avatars.serverless.config import ServerlessConfig
from avatars.serverless.executor import (
    JobExecutor,
    PlannedRun,
    map_engine_exception,
    write_traceback,
)
from avatars.serverless.store import JobRecord, ServerlessStore, SetRecord
from avatars.serverless.workdir import INPUT_VOLUME, RESULTS_VOLUME, Workdir

logger = get_logger(__name__)

# `avatar.models.results.RESULTS_FILENAME`, duplicated rather than imported so this
# module stays engine-free and unit-testable without the engine.
RESULTS_FILENAME = "results.json"

# The identity a serverless run reports when no licence names anyone (only in tests:
# the engine refuses to run without one). `Manager._verify_connection` calls
# `users.get_me()`, and `Runner` stamps the user id into run metadata.
SERVERLESS_USER_EMAIL = "serverless@localhost"


@dataclass(frozen=True)
class LicenseSummary:
    """What the licence in force grants, as the engine verified it.

    Read with ``Manager.license_info()``. Also the user that ``get_me()`` reports, and
    the licence ``jti`` recorded with every job. For display and attribution only: the
    engine has made every decision already.
    """

    email: str
    organization: str
    jti: str
    license_type: str
    feature_scopes: tuple[str, ...]
    max_rows: int
    max_columns: int
    expires_at: datetime

    def __str__(self) -> str:
        def limit(value: int, unit: str) -> str:
            return "no limit" if value >= _NO_LIMIT else f"{value:,} {unit} per dataset"

        rows = [
            ("Licensed to", self.email),
            ("Organization", self.organization),
            ("Tier", self.license_type),
            ("Features", ", ".join(self.feature_scopes) or "none"),
            ("Rows", limit(self.max_rows, "rows")),
            ("Columns", limit(self.max_columns, "columns")),
            ("Expires", f"{self.expires_at:%Y-%m-%d %H:%M} UTC"),
            ("Licence id", self.jti),
        ]
        return "\n".join(f"{label:<13}{value}" for label, value in rows)


# The licence's "no limit": a cap at or above it is shown as no limit.
_NO_LIMIT = 2**31 - 1


def _stable_id(kind: str, name: str) -> UUID:
    # The same licensee gets the same ids in every session, so run metadata from two
    # sessions names the same user.
    return uuid5(NAMESPACE_URL, f"avatar-serverless:{kind}:{name}")


class NotAvailableOfflineError(NotImplementedError):
    """Raised for the parts of the API that need a server to mean anything."""

    def __init__(self, what: str) -> None:
        super().__init__(
            f"{what} requires an Avatar server; this Manager is running in serverless mode."
        )


class _Unavailable:
    """Stands in for a resource client that serverless cannot provide.

    Present rather than absent so that reaching for one produces an explanation
    instead of ``AttributeError``, which would read as a bug in the SDK.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, item: str) -> Any:
        # Protocol and introspection lookups (copy, pickle, hasattr on __iter__...)
        # must see a missing attribute, not an API call to refuse.
        if item.startswith("__") and item.endswith("__"):
            raise AttributeError(item)
        raise NotAvailableOfflineError(f"{self._name}.{item}()")


class ServerlessResources:
    """``/resources`` -- stores the YAML a ``Runner`` uploads, with volumes injected."""

    def __init__(self, client: "ServerlessClient") -> None:
        self._client = client

    def put_resources(self, display_name: str, yaml_string: str) -> ResourceSetResponse:
        """Store a set's YAML, adding the volumes the server would have added.

        The SDK never emits volume documents -- ``Runner`` does not call
        ``create_volume``/``create_results_volume`` -- because on a server the volumes
        are the *deployment's* business: they point into the user's own storage area.
        ``ResourceManager._add_input_volume`` and ``_add_and_replace_result_volume``
        append them server-side. Serverless is its own deployment, so it does the
        same, with local paths.
        """
        from avatar_yaml import get_volume  # noqa: PLC0415

        # A run that reads a database or documents declares an `input` in a parameters
        # document. Neither is offered offline yet, and such a run is not bounded by the
        # licence's row and column caps, so it is refused before anything is stored.
        if _reads_through_input_protocol(yaml_string):
            raise NotAvailableOfflineError("Reading a database or documents")

        workdir = self._client.workdir
        set_name = uuid4()
        workdir.prepare_set(set_name)

        document = yaml_string.rstrip()
        document += "\n---\n" + get_volume(name=INPUT_VOLUME, url=workdir.input_url)
        document += "\n---\n" + get_volume(name=RESULTS_VOLUME, url=workdir.results_url(set_name))

        workdir.resources_path(set_name).write_text(document)
        self._client.store.add_set(SetRecord(set_name=set_name, display_name=display_name))
        logger.debug("serverless set stored", set_name=str(set_name), display_name=display_name)
        return ResourceSetResponse(set_name=set_name, display_name=display_name)

    def get_resources(self, set_name: str) -> str:
        path = self._client.workdir.resources_path(set_name)
        if not path.is_file():
            raise ValueError(f"No resource set '{set_name}' in {self._client.workdir.root}")
        return path.read_text()


class ServerlessJobs:
    """``/jobs`` -- served from the local store."""

    def __init__(self, client: "ServerlessClient") -> None:
        self._client = client

    def get_jobs(
        self,
        kind: list[JobKind] | None = None,
        display_name: str | None = None,
        set_name: str | None = None,
        names: list[str] | None = None,
        limit: int | None = None,
        include_deleted: bool | None = None,
    ) -> JobResponseList:
        records = self._client.store.find_jobs(
            kind=kind,
            display_name=display_name,
            set_name=set_name,
            names=names,
            limit=limit,
            include_deleted=bool(include_deleted),
        )
        return JobResponseList(jobs=[r.to_response() for r in records])

    def get_last_jobs(self) -> JobResponseList:
        return JobResponseList(jobs=[r.to_response() for r in self._client.store.last_set_jobs()])

    def get_job_status(self, job_name: str) -> JobResponse:
        record = self._client.store.get_job(job_name)
        if record is None:
            raise ValueError(f"No job '{job_name}' in {self._client.workdir.root}")
        return record.to_response()

    def cancel_job(self, job_name: str) -> JobResponse:
        # Jobs run to the end inside the request that creates them, so by the time
        # anyone can ask, every job is over: the server's 409.
        record = self._client.store.get_job(job_name)
        if record is None:
            raise ValueError(f"No job '{job_name}' in {self._client.workdir.root}")
        raise ValueError(f"Job '{job_name}' cannot be cancelled: it is already over")

    def bulk_delete_jobs(self, request: BulkDeleteRequest) -> BulkDeleteResponse:
        store = self._client.store
        deleted: list[JobResponse] = []
        failed: list[str] = []
        for name in request.job_names:
            # Read the record before deleting: the response carries the jobs, not
            # their names, and a soft-deleted record still answers `to_response`.
            record = store.get_job(name)
            if record is not None and store.soft_delete(name):
                deleted.append(record.to_response())
            else:
                failed.append(name)
        return BulkDeleteResponse(deleted_jobs=deleted, failed_jobs=failed)


class ServerlessResults:
    """``/results``, ``/access`` and ``/upload_url``, over the local filesystem."""

    def __init__(self, client: "ServerlessClient") -> None:
        self._client = client

    def get_upload_url(self) -> str:
        return self._client.workdir.input_url

    def get_permission_to_download(self, url: str) -> FileAccess:
        # There is nothing to authorise and no credentials to mint: the file is on
        # this disk. The URL is echoed unchanged, exactly as the server does when it
        # is handed an envelope it already issued.
        return FileAccess(url=url, credentials=_NO_CREDENTIALS)

    def get_permissions_to_download_batch(self, urls: list[str]) -> list[FileAccess]:
        return [self.get_permission_to_download(url) for url in urls]

    def get_results(self, job_name: str) -> dict[str, list[str]]:
        """The result URLs for a job, in the shape ``/results/{job}`` returns.

        Mirrors ``ResultStorageFacade.get_results``: read the job's ``results.json``,
        drop the internal kinds, and wrap every path in an ``/access?url=`` envelope.
        """
        client = self._client
        record = client.store.get_job(job_name)
        if record is None:
            raise ValueError(f"No job '{job_name}' in {client.workdir.root}")

        # The engine writes under ``<results volume>/<results.path>``, and the path is
        # whatever the job's parameters document says -- not always its name: advice
        # documents are named ``advice_parameters`` but write to ``advice``. Read from
        # the document, as ``ResultsService.get_results_directory`` does on the server.
        results_dir = client.workdir.results_dir(record.set_name) / _results_path(
            client.workdir.resources_path(record.set_name), record.parameters_name
        )
        results_file = results_dir / RESULTS_FILENAME
        if not results_file.is_file():
            # ``Runner._populate_results_from_existing_jobs`` matches on BOTH of these
            # substrings to tell "this job wrote nothing yet" (warn) from a real error
            # (re-raise). Changing this wording changes that behaviour.
            raise ValueError(
                f"Request failed with error status 404: results file for job "
                f"'{job_name}' not found in {results_dir}"
            )

        raw: dict[str, list[str]] = json.loads(results_file.read_text())
        internal = _internal_result_kinds()
        return {
            kind: [
                map_to_access_url(client.base_url, f"file://{results_dir / item}")
                for item in items
            ]
            for kind, items in raw.items()
            if kind not in internal
        }


class ServerlessUsers:
    def __init__(self, client: "ServerlessClient") -> None:
        self._client = client

    def get_me(self) -> MeUser:
        return self._client.user


class ServerlessHealth:
    def __init__(self, client: "ServerlessClient") -> None:
        self._client = client

    def get_health(self) -> dict[str, str]:
        return {"status": "ok", "mode": "serverless", "workdir": str(self._client.workdir.root)}


class ServerlessCompatibility:
    """``/check_client`` -- answers with the client range the engine declares, if any.

    The installed engine declares no range yet, so this answers ``compatible``: an SDK
    that writes a document the engine cannot parse is not caught here, but when the
    engine reads it. ``compatible=`` on ``ServerlessClient`` is where a declared range
    goes once the engine has one.
    """

    def __init__(self, client: "ServerlessClient") -> None:
        self._client = client

    def is_client_compatible(self) -> CompatibilityResponse:
        declared = self._client.compatibility_declared_by_engine
        if declared is not None:
            return declared
        return CompatibilityResponse(
            message="Serverless mode: the installed engine declares no client range.",
            most_recent_compatible_client=None,
            status=CompatibilityStatus.compatible,
        )


_NO_CREDENTIALS = FileCredentials(access_key_id="", secret_access_key="")


class ServerlessClient:
    """The in-process stand-in for :class:`avatars.client.ApiClient`."""

    def __init__(
        self,
        *,
        settings: ServerlessConfig,
        workdir: Workdir,
        store: ServerlessStore,
        executor: JobExecutor,
        engine_version: str | None = None,
        compatible: CompatibilityResponse | None = None,
        licensee: LicenseSummary | None = None,
    ) -> None:
        self.settings = settings
        self.licensee = licensee
        self.workdir = workdir
        self.store = store
        self.executor = executor
        self.engine_version = engine_version
        self.compatibility_declared_by_engine = compatible

        self.base_url = SERVERLESS_BASE_URL
        self.should_verify_ssl = True

        self.resources = ServerlessResources(self)
        self.jobs = ServerlessJobs(self)
        self.results = ServerlessResults(self)
        self.users = ServerlessUsers(self)
        self.health = ServerlessHealth(self)
        self.compatibility = ServerlessCompatibility(self)

        # Present, and explicit about why they are not usable. See _Unavailable.
        self.api_keys = _Unavailable("api_keys")
        self.event_logs = _Unavailable("event_logs")
        self.capabilities = _Unavailable("capabilities")
        self.openapi = _Unavailable("openapi")
        self.connections = _Unavailable("connections")
        self.documents = _Unavailable("documents")

        email = licensee.email if licensee else SERVERLESS_USER_EMAIL
        organization = licensee.organization if licensee else SERVERLESS_USER_EMAIL
        self.user = MeUser(
            id=_stable_id("user", email),
            organization_id=_stable_id("organization", organization),
            email=email,
            role=UserRole.user,
            environment=EnvironmentInfo(
                # Nothing expires offline. The limits are the licence's, reported as the
                # server reports its own; the engine is what enforces them.
                dataset_expiration_days=0,
                max_allowed_dimensions_per_dataset=licensee.max_columns if licensee else 0,
                max_allowed_lines_per_dataset=licensee.max_rows if licensee else 0,
                license_type=licensee.license_type if licensee else None,
            ),
        )

    # -- the two things BaseClient provides that the SDK calls directly ---------------

    def is_using_api_key(self) -> bool:
        # The licence is the credential. Manager checks this before anything else, and
        # a serverless client that got as far as being constructed has one.
        return True

    def send_request(self, *, method: str, url: str, **kwargs: Any) -> Any:
        """The raw escape hatch ``JobLauncher`` uses to create a job.

        Only ``POST /jobs`` is served. Anything else is a call the SDK was not
        expected to make, and guessing at it would be worse than saying so.
        """
        if method.lower() == "post" and url == "/jobs":
            request = kwargs["json_data"]
            if not isinstance(request, JobCreateRequest):
                request = JobCreateRequest.model_validate(request)
            return self._create_job(request).model_dump(by_alias=True)
        raise NotAvailableOfflineError(f"{method.upper()} {url}")

    # -- upload / download -------------------------------------------------------------

    def upload_file(self, data: str | pd.DataFrame, key: str) -> None:
        """Write a table into the input volume.

        Deliberately not routed through ``DataUploader``: that class exists to obtain
        S3 credentials and stream through ``fsspec``, and every step of it is a no-op
        against a local directory. Writing the file is the whole operation.
        """
        destination = self.workdir.input_dir / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, pd.DataFrame):
            data.reset_index(drop=True).to_parquet(destination, index=False)
        elif isinstance(data, str):
            # Copied, not read whole: an input file can be larger than memory.
            shutil.copyfile(data, destination)
        else:
            raise ValueError(
                f"Expected a path to a file or a pandas dataframe to upload, got {type(data)}"
            )

    def download_file(self, file_access: FileAccess) -> str | bytes:
        """Read a result back. Mirrors ``DataUploader.download_file``'s text/bytes split."""
        path = Path(to_local_path(file_access.url))
        if path.suffix in (".pdf", ".docx", ".parquet"):
            return path.read_bytes()
        return path.read_text(encoding="utf-8")

    def list_input_files(self) -> InputFiles:
        """The files of the input volume, newest first, as ``DataUploader`` lists them.

        A local directory has no retention rule, so no file carries an expiry.
        """
        entries = [
            {"name": str(path), "size": path.stat().st_size, "mtime": path.stat().st_mtime}
            for path in self.workdir.input_dir.iterdir()
            if path.is_file()
        ]
        return input_files_listing(self.workdir.input_url, entries)

    # -- resources ----------------------------------------------------------------------

    def _create_job(self, request: JobCreateRequest) -> JobCreateResponse:
        """Register a job and run it, now, on this thread.

        Synchronous on purpose. ``Runner.run()`` launches and returns without waiting,
        and the polling that follows (``_retrieve_job_result_urls``) uses a tenacity
        retry that does not sleep before its first attempt -- so a job that has already
        finished by the time ``run()`` returns costs nothing in latency, and the first
        status read is the final one.

        The alternative, a worker thread, buys nothing here and costs a great deal:
        ``Environment`` subclasses ``threading.local``, an exception on a background
        thread in a notebook is a log line nobody reads, and ``runner.run(); runner
        .shuffled(t)`` in a single cell becomes a race.
        """
        set_record = self.store.get_set(request.set_name)
        if set_record is None:
            raise ValueError(f"No resource set '{request.set_name}' in {self.workdir.root}")

        record = JobRecord(
            name=str(uuid4()),
            set_name=request.set_name,
            display_name=set_record.display_name,
            parameters_name=request.parameters_name,
            kind=_job_kind_for(
                self.workdir.resources_path(request.set_name), request.parameters_name
            ),
            depends_on=[_job_name_from_location(loc) for loc in (request.depends_on or [])],
            license_jti=self.licensee.jti if self.licensee else None,
        )
        self.store.add_job(record)
        self._run_job(record)
        return JobCreateResponse(name=record.name, Location=f"/jobs/{record.name}")

    def _run_job(self, record: JobRecord) -> None:
        """Execute a job and record what happened. Never raises.

        A failure here has to land in the job's ``status``/``exception``, not propagate
        out of ``send_request``: that is what the server does, and ``Runner`` is
        written against it -- ``run()`` returns, ``statuses()`` shows the error, and
        ``shuffled()`` raises with the message. Letting the exception escape instead
        would abort the whole ``run()`` and leave later jobs uncreated.
        """
        failed_parents = [
            name
            for name in record.depends_on
            if (parent := self.store.get_job(name)) is not None
            and parent.status != JobStatus.finished
        ]
        if failed_parents:
            record.status = JobStatus.parent_error
            record.done = True
            record.exception = (
                f"Error in job '{record.parameters_name}': a job it depends on did not finish."
            )
            self.store.update_job(record)
            return

        try:
            self.executor.execute(self._plan(record))
        except (KeyboardInterrupt, SystemExit):
            # Interrupting a long avatarization must interrupt, not be filed as a job
            # failure -- but the record must not be left claiming the job is still
            # pending either, or a later `statuses()` would hang waiting for it.
            record.status = JobStatus.error
            record.exception = f"Job '{record.parameters_name}' was interrupted."
            record.done = True
            self.store.update_job(record)
            raise
        except Exception as exc:
            status, message = map_engine_exception(record.parameters_name, exc)
            write_traceback(self.workdir.log_path(record.name), record.name, exc)
            record.status = status
            record.exception = message
            record.done = True
            record.progress = None
            self.store.update_job(record)
            # Surface it now: in a notebook, a silent failure four minutes before the
            # user calls shuffled() is a confusing way to learn about it.
            logger.exception(
                "serverless job failed",
                job=record.parameters_name,
                error=message,
                traceback_at=str(self.workdir.log_path(record.name)),
            )
            return

        record.status = JobStatus.finished
        record.done = True
        record.progress = 1.0
        record.exception = ""
        self.store.update_job(record)

    def _plan(self, record: JobRecord) -> PlannedRun:
        """Resolve a job's dependencies into the parameters hierarchy the engine wants.

        Mirrors ``JobService._extract_parameters_hierarchy``: ``depends_on`` names
        jobs, but ``create_dependent_config`` takes *parameters* names, and a report
        additionally needs to know what each of its parents itself depended on.
        """
        parents: list[str] = []
        grandparents: dict[str, str] = {}
        for parent_name in record.depends_on:
            parent = self.store.get_job(parent_name)
            if parent is None:
                continue
            parents.append(parent.parameters_name)
            for grandparent_name in parent.depends_on:
                grandparent = self.store.get_job(grandparent_name)
                if grandparent is not None:
                    grandparents[parent.parameters_name] = grandparent.parameters_name

        return PlannedRun(
            job_name=record.name,
            parameters_name=record.parameters_name,
            yaml_path=self.workdir.resources_path(record.set_name),
            results_url=self.workdir.results_url(record.set_name),
            parent_parameters=parents,
            grandparent_parameters=grandparents,
        )

    # -- results ------------------------------------------------------------------------------


def _job_name_from_location(location: str) -> str:
    """``/jobs/<name>`` -> ``<name>``. The SDK passes Locations in ``depends_on``."""
    return location.rsplit("/", 1)[-1]


# What each parameters document kind runs as. Mirrors ``map_model_kind_to_job_kind``
# on the server, which keys on the same document kinds.
_JOB_KIND_BY_DOCUMENT_KIND = {
    ModelKind.AVATARIZATION_PARAMETERS.value: JobKind.standard,
    ModelKind.PRIVACY_METRICS_PARAMETERS.value: JobKind.privacy_metrics,
    ModelKind.SIGNAL_METRICS_PARAMETERS.value: JobKind.signal_metrics,
    ModelKind.REPORT.value: JobKind.report,
    ModelKind.ADVICE.value: JobKind.advice,
}


def _reads_through_input_protocol(yaml_string: str) -> bool:
    """Whether a parameters document reads its data from a database or documents."""
    return any(
        isinstance(document, dict) and ((document.get("spec") or {}).get("input")) is not None
        for document in yaml.safe_load_all(yaml_string)
    )


def _parameters_document(resources_path: Path, parameters_name: str) -> dict[str, Any] | None:
    """The document named ``parameters_name`` in a set's ``resources.yaml``, if any."""
    if not resources_path.is_file():
        return None
    for document in yaml.safe_load_all(resources_path.read_text()):
        if (
            isinstance(document, dict)
            and document.get("kind") in _JOB_KIND_BY_DOCUMENT_KIND
            and (document.get("metadata") or {}).get("name") == parameters_name
        ):
            return document
    return None


def _results_path(resources_path: Path, parameters_name: str) -> str:
    """Where, under the results volume, a job writes: the document's ``results.path``.

    Falls back to the parameters name, which is what ``avatar_yaml`` writes for every
    kind but advice.
    """
    document = _parameters_document(resources_path, parameters_name) or {}
    path = ((document.get("spec") or {}).get("results") or {}).get("path")
    return str(path) if path else parameters_name


def _job_kind_for(resources_path: Path, parameters_name: str) -> JobKind:
    """The kind of job a parameters document runs as, read from its ``kind``.

    Without a document to read, the name decides: ``Runner`` names its documents after
    the job kind (``JobLauncher.get_parameters_name``). Anything unrecognised is a
    ``standard`` job, matching ``map_model_kind_to_job_kind``.
    """
    document = _parameters_document(resources_path, parameters_name)
    if document is not None:
        return _JOB_KIND_BY_DOCUMENT_KIND[str(document["kind"])]
    try:
        return JobKind(parameters_name)
    except ValueError:
        for prefix in (JobKind.report, JobKind.advice):
            if parameters_name.startswith(prefix.value):
                return prefix
        return JobKind.standard


def _internal_result_kinds() -> frozenset[str]:
    """Result kinds the server never exposes: holdout halves and augmentation mapping.

    Imported from the engine when it is installed so the two cannot drift, with a
    literal fallback so this module stays importable -- and unit-testable -- without
    the engine.
    """
    try:
        from avatar.models.results import INTERNAL_RESULT_KINDS  # noqa: PLC0415

        return frozenset(str(kind) for kind in INTERNAL_RESULT_KINDS)
    except ImportError:
        return frozenset(
            {
                "holdout_original",
                "holdout_working_half_original",
                "holdout_working_half_avatars",
                "data_augmentation_mapping",
            }
        )


def _serverless_client_satisfies_protocol(client: ServerlessClient) -> SdkClient:
    """Compile-time proof that the in-process client is interchangeable with the real one.

    The mirror image of ``avatars.sdk_client._generated_client_satisfies_protocol``.
    Between them, a change to the generated client fails on one and a change to this
    one fails on the other, so the two can never drift apart silently.
    """
    return client
