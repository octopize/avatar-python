"""What a database run's subjects joined, read back from the engine's result.

A subject declared on the wrong key column succeeds: every person gets an
identity of their own in each table and nothing fails. The engine writes the
counts that show it beside the export, and this is how a caller reads them.
"""

from __future__ import annotations

from typing import Any

import pytest

from avatars.constants import RESULTS_TO_STORE, Results, mapping_result_to_file_name
from avatars.manager import Manager
from avatars.results_organizer import ResultsOrganizer
from avatars.runner import Runner
from tests.unit.conftest import FakeApiClient

_TABLE = "crm_dot_customer"


def _report() -> dict[str, Any]:
    """The shape the engine writes to `<table>.reference_tables.json`."""
    return {
        "tables": {
            "rt_person": {
                "subjects": 12,
                "sources": [
                    {"table": "crm.customer", "rows": 12, "subjects": 12},
                    {"table": "billing.invoice", "rows": 24, "subjects": 12},
                ],
                "in_one_source_only": 0,
                "conflicting_subjects": 1,
                "conflicting_attributes": {"email": 1},
                "unresolved_rows": 0,
            }
        }
    }


def test_reference_tables_is_a_known_result_kind() -> None:
    assert Results.REFERENCE_TABLES.value == "reference_tables"
    assert Results.REFERENCE_TABLES in RESULTS_TO_STORE
    assert mapping_result_to_file_name[Results.REFERENCE_TABLES] == "reference_tables.json"


def test_the_report_is_filed_under_the_table_its_filename_names() -> None:
    organizer = ResultsOrganizer()
    url = f"s3://bucket/results/standard/{_TABLE}.reference_tables.json"

    name = organizer.get_table_name(Results.REFERENCE_TABLES, url, [_report()])
    assert name == _TABLE
    organizer.set_results(Results.REFERENCE_TABLES, [_report()], name)

    # Unescaped, like every table name the organizer keeps.
    assert organizer.reference_tables == {"crm.customer": _report()["tables"]}
    assert (
        organizer.get_results(_TABLE, Results.REFERENCE_TABLES, "standard") == _report()["tables"]
    )


def test_an_unfetched_report_reads_as_absent() -> None:
    """None, so `get_specific_result` knows to fetch it."""
    assert ResultsOrganizer().get_results("other", Results.REFERENCE_TABLES, "job") is None


def test_a_malformed_report_reads_as_empty_rather_than_raising() -> None:
    organizer = ResultsOrganizer()
    organizer.set_results(Results.REFERENCE_TABLES, {"unexpected": True}, _TABLE)

    assert organizer.reference_tables["crm.customer"] == {}


@pytest.fixture
def fetching(monkeypatch: pytest.MonkeyPatch) -> tuple[Runner, list[Results]]:
    """A runner whose download files the report, and the fetches it made."""
    runner = Manager(api_client=FakeApiClient()).create_runner("crm")
    fetched: list[Results] = []

    def download(job_name: str, result_name: Results) -> None:
        fetched.append(result_name)
        runner.results.set_results(result_name, [_report()], _TABLE)

    monkeypatch.setattr(runner, "_download_specific_result", download)
    return runner, fetched


def test_the_runner_finds_the_report_without_being_told_the_table(
    fetching: tuple[Runner, list[Results]],
) -> None:
    runner, _ = fetching
    assert runner.reference_tables_report() == _report()["tables"]


def test_the_runner_fetches_the_report_once(fetching: tuple[Runner, list[Results]]) -> None:
    runner, fetched = fetching
    runner.reference_tables_report()
    runner.reference_tables_report()

    assert fetched == [Results.REFERENCE_TABLES]
