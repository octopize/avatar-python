"""Where a serverless run keeps its files.

The layout mirrors the server's, so that the YAML the SDK produces means the same
thing here as it does there:

.. code-block:: text

    <root>/
        index.json                     the job/set store
        input/                         the "input" volume, shared across sets
            patients.csv
        sets/<set_name>/
            resources.yaml             the YAML as stored, with volumes injected
            results/                   the "results" volume for this set
                standard/ privacy_metrics/ signal_metrics/ report/
        logs/<job_name>.log            the traceback of a failed job

``input`` is deliberately outside ``sets/``: on the server
``StorageLocation.for_user(purpose="input")`` carries no ``set_name`` segment, so a
table uploaded once is visible to every later run. Re-running a set must not oblige
the caller to re-upload.
"""

from pathlib import Path
from uuid import UUID

# The volume names the SDK's YAML refers to. They are not free choices: `Runner`
# never calls `create_volume`/`create_results_volume`, so `avatar_yaml` falls back to
# its own defaults (`INPUT_VOLUME_NAME` / `OUTPUT_VOLUME_NAME`) when it writes the
# `results:` block of every parameters document.
INPUT_VOLUME = "input"
RESULTS_VOLUME = "results"


class Workdir:
    """The directory a serverless ``Manager`` reads and writes."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def ensure(self) -> "Workdir":
        """Create the directories that must exist before anything runs."""
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.sets_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        return self

    # -- directories -------------------------------------------------------------

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def sets_dir(self) -> Path:
        return self.root / "sets"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    def set_dir(self, set_name: str | UUID) -> Path:
        return self.sets_dir / str(set_name)

    def resources_path(self, set_name: str | UUID) -> Path:
        return self.set_dir(set_name) / "resources.yaml"

    def results_dir(self, set_name: str | UUID) -> Path:
        return self.set_dir(set_name) / "results"

    def log_path(self, job_name: str) -> Path:
        return self.logs_dir / f"{job_name}.log"

    # -- URLs --------------------------------------------------------------------
    #
    # `file://` rather than a bare path: `avatars.storage.get_filesystem` hands these
    # to `fsspec.url_to_fs`, which returns a LocalFileSystem for either spelling, but
    # the engine's own `Environment` also parses `SHARED_STORAGE` by scheme.

    @property
    def input_url(self) -> str:
        return f"file://{self.input_dir}"

    def results_url(self, set_name: str | UUID) -> str:
        return f"file://{self.results_dir(set_name)}"

    def prepare_set(self, set_name: str | UUID) -> Path:
        """Create the per-set directories and return the set's own directory."""
        self.results_dir(set_name).mkdir(parents=True, exist_ok=True)
        return self.set_dir(set_name)
