"""Run every Python snippet of the user guide against a fake API client.

Each page runs its blocks in order, in one namespace, like a reader who copies
them one after the other. The blocks run one top-level statement at a time, so
that a statement that the fake server cannot answer skips only itself. Such a
statement must match an entry of FAKE_LIMITS.
"""

import ast
import json
import re
import warnings
import webbrowser
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest

import avatars.manager
from avatars.client_config import ClientConfig
from avatars.constants import PlotKind
from avatars.models import JobKind
from tests.unit.conftest import FakeApiClient, FakeResources, FakeResults, create_fake_job

CLIENT_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = CLIENT_DIR / "fixtures"
USER_GUIDE_DIR = CLIENT_DIR / "doc" / "source" / "user_guide"
PAGES = sorted(USER_GUIDE_DIR.glob("*.md"))

# Table used in the snippets -> fixture whose rows the fake server returns as avatars.
TABLE_FIXTURES = {
    "wbcd": "wbcd.csv",
    "iris": "iris.csv",
    "adult": "adult_with_missing.csv",
    "people": "pseudo_data.csv",
    "patient": "patient.csv",
    "doctor": "doctor.csv",
    "visit": "visit.csv",
    "individuals": "sensors_vanilla.csv",
    "sensor": "sensors_timeseries1.csv",
}
TABLES = [*TABLE_FIXTURES, "players", "stays", "my_table"]
# Runs that the snippets reload by name, as if they had run before.
RELOADED_RUN_NAMES = ["wbcd_tuning", "my_web_job", "my_run"]
RELOADED_JOB_KINDS = [
    JobKind.standard,
    JobKind.privacy_metrics,
    JobKind.signal_metrics,
    JobKind.report,
]
# Links that the fake links advice proposes: parent table -> (parent key, child table, child key).
ADVISED_LINKS = {
    "patient": ("p_id", "visit", "patient_id"),
    "doctor": ("d_id", "visit", "doctor_id"),
}

# Context for the pages whose snippets use a `manager` or a `runner` they do not create.
PRELUDE = """
from avatars.manager import Manager

manager = Manager(api_key="test-key")
runner = manager.create_runner("prelude")
runner.add_table("wbcd", "fixtures/wbcd.csv")
runner.advise_parameters("wbcd")
runner.run()
"""

# (page, part of the error message) -> answer that the fake server does not give.
FAKE_LIMITS = {
    ("metrics.md", "only available for multi-table jobs"): "single-table runner in the setup",
}

PYTHON_BLOCK = re.compile(r"^( *)```python\n(.*?)^\1```", re.DOTALL | re.MULTILINE)


class DocsFakeResults(FakeResults):
    """Serve the results of every job, whatever its name, with a figure of each kind."""

    def get_results(self, job_name: str) -> dict[str, list[str]]:
        if "tables_links" in job_name:
            return {"advice": [f"fakeurl/{table}.links_advice.json" for table in self.tables]}
        results: dict[str, list[str]] = super().get_results(  # type: ignore[no-untyped-call]
            job_name.split("@", maxsplit=1)[0]
        )
        if "figures" in results:
            results["figures"] = [
                f"fakeurl/{table}.{kind.value}.html" for table in self.tables for kind in PlotKind
            ]
        return results


class DocsFakeResources(FakeResources):
    """Serve a configuration with all the tables for the reloaded runs."""

    reloaded_yaml = ""

    def get_resources(self, set_name: str) -> str:
        if set_name in self._stored_resources:
            return self._stored_resources[set_name]
        return self.reloaded_yaml


class FakeApiKeys:
    def create_api_key(self, request: Any) -> dict[str, Any]:
        return {"api_key": {"plaintext": "octopize_apikey.fake"}}


class DocsFakeApiClient(FakeApiClient):
    def __init__(self, api_key: str | None) -> None:
        super().__init__(tables=TABLES)
        self._api_key = api_key
        self.results = DocsFakeResults(tables=TABLES)  # type: ignore[assignment]
        self.resources = DocsFakeResources()  # type: ignore[assignment,no-untyped-call]
        self.api_keys = FakeApiKeys()  # type: ignore[assignment]
        for run_name in RELOADED_RUN_NAMES:
            set_name = uuid4()
            for kind in RELOADED_JOB_KINDS:
                self.jobs.add_job(
                    create_fake_job(
                        name=f"{kind.value}@{run_name}",
                        set_name=set_name,
                        display_name=run_name,
                        kind=kind,
                    )
                )

    def download_file(self, file_access: Any) -> Any:
        filename = Path(file_access.url).name
        table_name = filename.split(".")[0]
        if filename == "figures_metadata.json":
            return json.dumps(
                [
                    {
                        "kind": kind.value,
                        "filename": f"{table}.{kind.value}.html",
                        "table_name": table,
                    }
                    for table in self.tables
                    for kind in PlotKind
                ]
            )
        if filename.endswith(".links_advice.json"):
            links = []
            if table_name in ADVISED_LINKS:
                parent_field, child_table, child_field = ADVISED_LINKS[table_name]
                links.append(
                    {
                        "field": parent_field,
                        "to": {"table": child_table, "field": child_field},
                        "method": "linear_sum_assignment",
                        "confidence": "high",
                    }
                )
            return json.dumps(
                {"table_name": table_name, "advice": {"links": links, "unlinked_foreign_keys": []}}
            )
        if filename.endswith(".advice.json"):
            advice = json.loads(super().download_file(file_access))  # type: ignore[no-untyped-call]
            advice["advice"]["summary"] = {"stats": [{"variable": "value", "type": "numeric"}]}
            return json.dumps(advice)
        is_avatar_table = ".shuffled-" in filename or ".unshuffled-" in filename
        if is_avatar_table and table_name in TABLE_FIXTURES:
            return (FIXTURES_DIR / TABLE_FIXTURES[table_name]).read_text()
        return super().download_file(file_access)  # type: ignore[no-untyped-call]


def _reloaded_yaml() -> str:
    runner = avatars.manager.Manager(api_client=FakeApiClient()).create_runner("reloaded")
    for table in TABLES:
        runner.add_table(table, pd.DataFrame({"value": [1, 2, 3]}))
        runner.set_parameters(table, k=3)
    return runner.get_yaml()


def _assigned_names(statement: ast.stmt) -> set[str]:
    return {
        node.id
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    DocsFakeResources.reloaded_yaml = _reloaded_yaml()

    def fake_api_client(*args: Any, config: ClientConfig | None = None, **kwargs: Any) -> Any:
        # The real Manager checks its arguments, then builds the client from them.
        api_key = config.api_key if config is not None else kwargs.get("api_key")
        return DocsFakeApiClient(api_key=api_key or None)

    monkeypatch.setattr(avatars.manager, "ApiClient", fake_api_client)
    monkeypatch.setattr(webbrowser, "open", lambda *args, **kwargs: True)
    monkeypatch.setenv("AVATAR_API_KEY", "test-key")
    (tmp_path / "fixtures").symlink_to(FIXTURES_DIR)
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("fake_server")
@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_user_guide_snippets_run(page: Path) -> None:
    namespace: dict[str, Any] = {}
    exec(PRELUDE, namespace)

    failures = []
    for index, (indent, block) in enumerate(PYTHON_BLOCK.findall(page.read_text())):
        code = "\n".join(line[len(indent) :] for line in block.splitlines())
        skipped_names: set[str] = set()
        for statement in ast.parse(code).body:
            location = f"block {index}, line {statement.lineno}"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    module = ast.Module(body=[statement], type_ignores=[])
                    exec(compile(module, f"{page.name}[{index}]", "exec"), namespace)
                except NameError as error:
                    if error.name not in skipped_names:
                        failures.append(f"{location}: NameError: {error}")
                except Exception as error:  # noqa: BLE001
                    is_fake_limit = any(
                        limit_page == page.name and message in str(error)
                        for limit_page, message in FAKE_LIMITS
                    )
                    if not is_fake_limit:
                        failures.append(f"{location}: {type(error).__name__}: {error}")
                    skipped_names |= _assigned_names(statement)

    assert not failures, "\n".join(failures)
