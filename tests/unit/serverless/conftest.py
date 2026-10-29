"""Fixtures for the serverless client, none of which need the engine installed.

``FakeEngineExecutor`` is what makes that possible: it writes the files a real run
would write, so the entire SDK chain -- volume injection, upload, job creation,
status, ``results.json``, the access envelope, download, ``ResultsOrganizer`` -- is
exercised end to end without importing ``avatar``.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from avatars.serverless.client import ServerlessClient
from avatars.serverless.config import ServerlessConfig
from avatars.serverless.executor import PlannedRun
from avatars.serverless.store import ServerlessStore
from avatars.serverless.workdir import Workdir

IRIS = pd.DataFrame(
    {
        "sepal_length": [5.1, 4.9, 4.7, 5.0, 5.4, 4.6, 5.2, 5.5],
        "sepal_width": [3.5, 3.0, 3.2, 3.6, 3.9, 3.4, 3.5, 4.2],
        "variety": ["a", "b", "a", "b", "a", "b", "a", "b"],
    }
)


class FakeEngineExecutor:
    """Writes what a real run writes, without running one.

    Records every ``PlannedRun`` it is handed, so tests can assert on the dependency
    hierarchy the client derived -- which is the part most likely to be wrong.
    """

    def __init__(self, table: str = "iris", fail_with: Exception | None = None) -> None:
        self.table = table
        self.fail_with = fail_with
        self.runs: list[PlannedRun] = []

    def execute(self, run: PlannedRun) -> None:
        self.runs.append(run)
        if self.fail_with is not None:
            raise self.fail_with

        # Where the real engine writes: the document's ``results.path``, which is not
        # always its name (advice documents write to ``advice``). Deriving it from the
        # name here is what once let the client make the same mistake unnoticed.
        results_dir = Path(run.results_url.removeprefix("file://")) / _results_path(
            run.yaml_path, run.parameters_name
        )
        results_dir.mkdir(parents=True, exist_ok=True)

        if run.parameters_name == "standard":
            IRIS.to_csv(results_dir / f"{self.table}.shuffled-0.csv", index=False)
            IRIS.to_csv(results_dir / f"{self.table}.unshuffled-0.csv", index=False)
            written = {
                "shuffled": [f"{self.table}.shuffled-0.csv"],
                "unshuffled": [f"{self.table}.unshuffled-0.csv"],
                # An internal kind, which get_results must drop.
                "holdout_original": [f"{self.table}.holdout-0.csv"],
            }
        elif run.parameters_name == "privacy_metrics":
            # Shape taken from a real run, not invented: ResultsOrganizer reads
            # `result[0]["metadata"]["table_name"]` to key metrics by table, so a
            # fake without `metadata` would pass here and fail against the engine.
            (results_dir / f"{self.table}.privacy.json").write_text(
                json.dumps(
                    {
                        "metadata": {"table_name": self.table, "computation_type": "standalone"},
                        "hidden_rate": 95.0,
                        "local_cloaking": 12.0,
                    }
                )
            )
            written = {"privacy_metrics": [f"{self.table}.privacy.json"]}
        elif run.parameters_name == "signal_metrics":
            (results_dir / f"{self.table}.signal.json").write_text(
                json.dumps(
                    {
                        "metadata": {"table_name": self.table, "computation_type": "standalone"},
                        "correlation_difference_ratio": 0.9,
                    }
                )
            )
            written = {"signal_metrics": [f"{self.table}.signal.json"]}
        elif run.parameters_name == "advice_parameters":
            # Shape taken from a real run: the recommendation sits under "advice".
            (results_dir / f"{self.table}.advice.json").write_text(
                json.dumps(
                    {
                        "table_name": self.table,
                        "advice": {
                            "k": 20,
                            "ncp": 3,
                            "use_categorical_reduction": False,
                            "imputation": None,
                        },
                    }
                )
            )
            written = {"advice": [f"{self.table}.advice.json"]}
        else:
            # Anything else "runs" but writes nothing, which is how a job with no
            # results behaves -- the case get_results has to report as a 404.
            return

        (results_dir / "results.json").write_text(json.dumps(written))


def _results_path(yaml_path: Path, parameters_name: str) -> str:
    for document in yaml.safe_load_all(yaml_path.read_text()):
        if (
            isinstance(document, dict)
            and (document.get("metadata") or {}).get("name") == parameters_name
        ):
            path = ((document.get("spec") or {}).get("results") or {}).get("path")
            if path:
                return str(path)
    return parameters_name


@pytest.fixture
def workdir(tmp_path: Path) -> Workdir:
    return Workdir(tmp_path / "wd").ensure()


@pytest.fixture
def store(workdir: Workdir) -> ServerlessStore:
    return ServerlessStore(workdir.index_path)


@pytest.fixture
def executor() -> FakeEngineExecutor:
    return FakeEngineExecutor()


@pytest.fixture
def client(
    workdir: Workdir, store: ServerlessStore, executor: FakeEngineExecutor
) -> ServerlessClient:
    return ServerlessClient(
        settings=ServerlessConfig(workdir=workdir.root),
        workdir=workdir,
        store=store,
        executor=executor,
    )
