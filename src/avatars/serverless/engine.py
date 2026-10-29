"""The only module that imports ``avatar``.

Everything requiring judgement lives on the other side of this line -- in
``executor.py``, ``store.py``, ``client.py`` -- so that it can be tested without the
``serverless`` extra installed. What is left here is deliberately thin: build a
config, build a context, call ``process``.

The engine surface this depends on is small and must stay frozen, because an
obfuscation pass that renames any of it breaks serverless silently at import:

* ``avatar.config.Config``
* ``avatar.models.config.load_configs``
* ``avatar.models.results.INTERNAL_RESULT_KINDS``
* ``avatar.processing.avatarize.process``
* ``avatar.processing.context.Context``
* ``avatar.processing.dependency.create_dependent_config``
* ``avatar.processing.environment.Environment``
* ``avatar.processing.progress.SimpleProgressTracker``
* ``avatar.task.executor_type.ExecutorType``

``process`` rather than ``external_process``: the latter hardcodes
``Environment(config=job.config)``, which defaults to the Dask executor and would
spawn the worker processes serverless exists to avoid.
"""

import os
import shutil
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from structlog import get_logger

from avatars.serverless.client import LicenseSummary
from avatars.serverless.config import ServerlessConfig
from avatars.serverless.executor import PlannedRun

logger = get_logger(__name__)


# The Python the distributed engine is compiled for (engine/build.py ENGINE_PYTHON).
ENGINE_PYTHON = (3, 14)


class EngineNotInstalledError(ImportError):
    """Raised when serverless mode is asked for without the engine."""

    def __init__(self, cause: BaseException | None = None) -> None:
        import sys  # noqa: PLC0415

        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        detail = f" ({cause})" if cause else ""
        # The engine is compiled for exactly one Python; anything else, older or newer,
        # cannot load it, and the fix is the environment rather than the install.
        if sys.version_info[:2] != ENGINE_PYTHON:
            needed = f"{ENGINE_PYTHON[0]}.{ENGINE_PYTHON[1]}"
            message = (
                f"Serverless mode needs the Avatar engine, which requires Python {needed}. "
                f"You are on Python {version}. Create a {needed} environment "
                f"(`uv venv --python {needed}`) and install the engine bundle that Octopize "
                f"supplies into it (`pip install -r requirements.txt`).{detail}"
            )
        else:
            message = (
                "Serverless mode needs the Avatar engine, which is not installed. "
                "Install the engine bundle that Octopize supplies "
                "(`pip install -r requirements.txt` in the bundle directory)."
                f"{detail}"
            )
        super().__init__(message)


class LicenseInfo(Protocol):
    """What the engine's licence module hands back once a key checks out.

    Defined structurally because the implementation lives inside the compiled engine
    -- this package must never contain verification logic, an embedded key, or any
    other part of the decision. ``services/client`` is mirrored verbatim into the
    public ``octopize/avatar-python`` repository on every release.
    """

    @property
    def user_email(self) -> str: ...

    @property
    def org_name(self) -> str: ...

    @property
    def license_type(self) -> str: ...

    @property
    def expires_at(self) -> "datetime": ...

    @property
    def jti(self) -> str: ...

    @property
    def feature_scopes(self) -> list[Any]: ...

    @property
    def max_allowed_lines_per_dataset(self) -> int: ...

    @property
    def max_allowed_dimensions_per_dataset(self) -> int: ...


@dataclass(frozen=True)
class EngineLimits:
    """The caps a run is subject to, and who it is licensed to.

    The identity fields are carried for display and for the audit trail -- a licence
    names a person, and a run that cannot say whose licence it used is a run nobody
    can be asked about later. They are never used to decide anything: the engine has
    already made every decision by the time this exists.
    """

    feature_scopes: list[Any]
    max_allowed_lines_per_dataset: int
    max_allowed_dimensions_per_dataset: int
    licensed_to: str
    organization: str
    license_type: str
    expires_at: "datetime"
    jti: str

    @classmethod
    def from_license(cls, info: LicenseInfo) -> "EngineLimits":
        return cls(
            feature_scopes=list(info.feature_scopes),
            max_allowed_lines_per_dataset=info.max_allowed_lines_per_dataset,
            max_allowed_dimensions_per_dataset=info.max_allowed_dimensions_per_dataset,
            licensed_to=info.user_email,
            organization=info.org_name,
            license_type=info.license_type,
            expires_at=info.expires_at,
            jti=info.jti,
        )

    def summary(self) -> LicenseSummary:
        """What ``Manager.license_info()`` shows: the same facts, for a person."""
        return LicenseSummary(
            email=self.licensed_to,
            organization=self.organization,
            jti=self.jti,
            license_type=self.license_type,
            feature_scopes=tuple(str(getattr(f, "value", f)) for f in self.feature_scopes),
            max_rows=self.max_allowed_lines_per_dataset,
            max_columns=self.max_allowed_dimensions_per_dataset,
            expires_at=self.expires_at,
        )


def require_engine() -> None:
    """Fail early, and legibly, if the engine is missing."""
    try:
        import avatar  # noqa: F401, PLC0415
    except ImportError as exc:
        raise EngineNotInstalledError(exc) from exc


def activate_license(license_key: str | None) -> EngineLimits:
    """Hand the key to the engine and keep whatever it says.

    The whole decision -- signature, expiry, scope, whether serverless is permitted
    at all -- happens inside the compiled engine. This function neither verifies nor
    interprets; it passes the key in and carries the answer out, so that a reader of
    the public mirror learns nothing about how licences are checked.

    An engine with no licensing module is refused, not run unlicensed: this public
    code must not decide that a run needs no licence.
    """
    require_engine()

    try:
        from avatar.licensing.runtime import activate  # noqa: PLC0415
    except ImportError as exc:
        raise EngineNotInstalledError(
            RuntimeError("the installed avatar engine has no licensing module")
        ) from exc

    limits = EngineLimits.from_license(activate(license_key))
    logger.info(
        "serverless licence activated",
        # The licence id, not the person: logs travel further than the notebook.
        expires_at=limits.expires_at.date().isoformat(),
        jti=limits.jti,
    )
    return limits


# Where the engine wheel puts the report renderer, relative to site-packages.
# With .exe on Windows, as engine/build.py names it there.
BUNDLED_REPORT_GENERATOR = "avatar/_bin/reportgenerator" + (
    ".exe" if sys.platform == "win32" else ""
)


def bundled_report_generator() -> str | None:
    """Absolute path of the report renderer shipped in the engine wheel, if any.

    Looked up through the wheel's own metadata rather than PATH: a Jupyter kernel
    started from a virtualenv does not necessarily have that venv's `bin/` on PATH.
    """
    try:
        from importlib.metadata import PackageNotFoundError, distribution  # noqa: PLC0415

        path = distribution("octopize-avatar-engine").locate_file(BUNDLED_REPORT_GENERATOR)
    except PackageNotFoundError:
        return None
    candidate = str(path)
    return candidate if os.path.isfile(candidate) and os.access(candidate, os.X_OK) else None


def resolve_report_generator(configured: str | None) -> str | None:
    """The renderer to use: explicit setting, then the bundled one, then PATH."""
    if configured:
        return configured
    return bundled_report_generator() or shutil.which("reportgenerator")


def engine_version() -> str | None:
    try:
        from importlib.metadata import version  # noqa: PLC0415

        return version("octopize-avatar-engine")
    except Exception:  # noqa: BLE001 - a missing version must never break a run
        return None


class EngineJobExecutor:
    """Runs one job through the real engine, in this process."""

    def __init__(
        self, settings: ServerlessConfig, limits: EngineLimits, seeding_salt: int, license_key: str
    ) -> None:
        self.settings = settings
        # Kept to check, before each job, that this Manager's licence is the one in
        # force: the engine holds one licence per process, and refuses any other.
        self.license_key = license_key
        self.limits = limits
        self.seeding_salt = seeding_salt
        self.report_generator = resolve_report_generator(settings.pdf_generator_binary)
        if self.report_generator is None:
            warnings.warn(
                "No report renderer found (none bundled in the engine, no `reportgenerator` "
                "on PATH). Report jobs will finish but produce Typst source instead of a PDF.",
                UserWarning,
                stacklevel=3,
            )

    def execute(self, run: PlannedRun) -> None:
        from avatar.config import Config as EngineConfig  # noqa: PLC0415
        from avatar.licensing.runtime import activate  # noqa: PLC0415
        from avatar.models.config import load_configs  # noqa: PLC0415
        from avatar.processing.avatarize import process  # noqa: PLC0415
        from avatar.processing.context import Context  # noqa: PLC0415
        from avatar.processing.dependency import create_dependent_config  # noqa: PLC0415
        from avatar.processing.environment import Environment  # noqa: PLC0415
        from avatar.processing.progress import SimpleProgressTracker  # noqa: PLC0415
        from avatar.task.executor_type import ExecutorType  # noqa: PLC0415

        activate(self.license_key)

        model_config, report_paths = create_dependent_config(
            load_configs(run.yaml_path.read_text()),
            run.parameters_name,
            run.parent_parameters,
            run.grandparent_parameters,
        )

        engine_config = EngineConfig(**self._config_kwargs(run))
        environment = Environment(
            exec_type=ExecutorType(self.settings.executor),
            config=engine_config,
        )
        context = Context(
            config=model_config,
            parameters_name=run.parameters_name,
            report_paths=report_paths,
        )

        logger.info("serverless job starting", job=run.parameters_name)
        process(environment, context, progress_tracker=SimpleProgressTracker())
        logger.info("serverless job finished", job=run.parameters_name)

    def _config_kwargs(self, run: PlannedRun) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "SHARED_STORAGE": run.results_url,
            # Not cosmetic: `avatar.config.Config` has a validator that rejects a
            # partially-set storage triple, and `Environment.__init__` only builds S3
            # fsspec kwargs when the endpoint is truthy. The API sets them empty for
            # local storage for exactly this reason.
            "STORAGE_ENDPOINT_URL": "",
            "STORAGE_ACCESS_KEY_ID": "",
            "STORAGE_SECRET_ACCESS_KEY": "",
            "SEEDING_SALT": self.seeding_salt,
            # Falls back to the engine's own default, which degrades to Typst source.
            "AVATAR_PDFGENERATOR_BINARY": self.report_generator or "reportgenerator",
        }

        # The licence's features and caps are not passed: with a licence in force, the
        # engine reads them from the licence, never from Config.
        # Omitted rather than set to None, so the engine's own default stands.
        if self.settings.batch_size is not None:
            kwargs["BATCH_SIZE"] = self.settings.batch_size

        return kwargs
