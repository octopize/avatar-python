"""A database run is launched only from a proposed schema the source agrees with.

The Schema discovery lists, beside its plan, each finding of the source's data contract and,
when it ran with an approved schema, each item of schema drift. The Extraction refuses such a
run once it has started; the client refuses to launch it.

The schema the client builds carries what the Extraction checks and what an Iceberg run needs:
each column's source type, the primary keys and the links.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
import pytest
import yaml
from avatar_yaml import run_shape

from avatars import ExtractionRefusedError, ProposalNotReadyError
from avatars.base_client import ApiResponseError
from avatars.constants import Results
from avatars.manager import Manager
from avatars.models import JobStatus
from avatars.results_organizer import ResultsOrganizer
from avatars.runner import Runner
from avatars.schema_items import (
    ContractFindingItem,
    ExtractionRefusal,
    SchemaDriftItem,
    SchemaDriftKind,
)
from avatars.schema_plan import SchemaPlan
from tests.unit.conftest import FakeApiClient, FakeResources

MESSAGE = "the data contract names the column customer.phone, which the source does not have"
FINDING: dict[str, Any] = {
    "kind": "missing_column",
    "table": "customer",
    "column": "phone",
    "contract_type": None,
    "discovered_type": None,
    "message": MESSAGE,
}


def _drift(kind: str, table: str, column: str | None = None, **types: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "table": table,
        "column": column,
        "approved_type": types.get("approved_type"),
        "discovered_type": types.get("discovered_type"),
        "message": f"{kind} {table}.{column}",
    }


def _tables() -> list[dict[str, Any]]:
    """Customers and their invoices, as discovery proposes them, every proposal confirmed."""
    return [
        {
            "name": "customer",
            "treatment": "anonymize",
            "individual_level": True,
            "cluster": "group-customer",
            "primary_key": ["id"],
            "links": [],
            "columns": [
                {"name": "id", "action": "keep", "column_type": "int", "source_type": "bigint"},
                {
                    "name": "age",
                    "action": "keep",
                    "column_type": "int",
                    "source_type": "integer",
                },
            ],
        },
        {
            "name": "invoice",
            "treatment": "anonymize",
            "cluster": "group-customer",
            "primary_key": ["id"],
            "links": [
                {
                    "column": "customer_id",
                    "references_table": "customer",
                    "references_column": "id",
                }
            ],
            "columns": [
                {"name": "id", "action": "keep", "column_type": "int", "source_type": "bigint"},
                {
                    "name": "customer_id",
                    "action": "keep",
                    "column_type": "int",
                    "source_type": "bigint",
                },
                {
                    "name": "total",
                    "action": "keep",
                    "column_type": "float",
                    "source_type": "double",
                },
            ],
        },
    ]


def _proposal(**facts: Any) -> dict[str, Any]:
    return {"tables": _tables(), **facts}


def _runner(plan: SchemaPlan) -> tuple[Runner, FakeResources]:
    client = FakeApiClient()
    resources = cast("FakeResources", client.resources)
    runner = Manager(api_client=client).create_runner("crm")
    runner.add_database(source="crm_prod", target="crm_test", plan=plan)
    runner.set_parameters(k=3, table_name="customer")
    runner.set_parameters(k=3, table_name="invoice")
    return runner, resources


class TestLaunch:
    def test_a_proposal_with_a_contract_finding_is_not_launched(self) -> None:
        runner, resources = _runner(
            SchemaPlan.from_proposal(_proposal(contract_findings=[FINDING]))
        )

        with pytest.raises(ProposalNotReadyError) as raised:
            runner.run()

        assert MESSAGE in str(raised.value)
        assert resources._stored_names == [], "nothing was stored or launched"

    def test_a_proposal_with_schema_drift_is_not_launched(self) -> None:
        drift = [
            _drift("new_table", "audit"),
            _drift("new_column", "customer", "phone"),
            _drift("missing_column", "invoice", "note"),
            _drift(
                "changed_type", "customer", "age", approved_type="integer", discovered_type="text"
            ),
        ]
        runner, resources = _runner(SchemaPlan.from_proposal(_proposal(schema_drift=drift)))

        with pytest.raises(ProposalNotReadyError) as raised:
            runner.run()

        message = str(raised.value)
        for item in drift:
            assert item["message"] in message
        assert "run the schema discovery again" in message
        assert raised.value.schema_drift == [SchemaDriftItem.model_validate(i) for i in drift]
        assert raised.value.contract_findings == []
        assert resources._stored_names == []

    def test_a_proposal_the_source_agrees_with_is_launched(self) -> None:
        runner, resources = _runner(
            SchemaPlan.from_proposal(_proposal(contract_findings=[], schema_drift=[]))
        )

        runner.run()

        assert resources._stored_names, "the set was stored"

    def test_an_item_of_a_kind_this_client_does_not_know_still_holds_the_run(self) -> None:
        plan = SchemaPlan.from_proposal(_proposal(schema_drift=[_drift("renamed_table", "x")]))

        with pytest.raises(ProposalNotReadyError, match="renamed_table x"):
            plan.require_launchable()

    def test_the_findings_follow_the_plan_into_each_group(self) -> None:
        plan = SchemaPlan.from_proposal(_proposal(contract_findings=[FINDING]))

        with pytest.raises(ProposalNotReadyError):
            plan.for_cluster("group-customer").require_launchable()


def test_the_proposal_s_findings_and_schema_drift_are_kept_with_its_plan() -> None:
    """The discovery files them beside its plan."""
    organizer = ResultsOrganizer()
    organizer.set_results(
        Results.ADVICE,
        [
            {
                "table_name": "schema_discovery",
                "advice": {"tables": _tables()},
                "clusters": [],
                "contract_findings": [FINDING],
                "schema_drift": [_drift("new_table", "audit")],
                "ready": False,
            }
        ],
        "schema_discovery",
    )

    plan = SchemaPlan.from_proposal(organizer.advice["schema_discovery"])

    assert plan.contract_findings == [ContractFindingItem.model_validate(FINDING)]
    assert [(item.kind, item.table) for item in plan.schema_drift] == [
        (SchemaDriftKind.new_table, "audit")
    ]
    assert plan.tables == ["customer", "invoice"]


def _schema(runner: Runner) -> dict[str, Any]:
    documents = [doc for doc in yaml.safe_load_all(runner.get_yaml()) if doc]
    return next(
        doc
        for doc in documents
        if doc.get("kind") == "AvatarSchema" and doc["metadata"]["name"] == "schema"
    )


class TestTheSchemaBuilt:
    def test_it_carries_the_primary_keys_and_the_links(self) -> None:
        runner, _ = _runner(SchemaPlan.from_proposal(_proposal()))

        tables = {table["name"]: table for table in _schema(runner)["spec"]["tables"]}

        keys = {
            name: [c["field"] for c in table["columns"] if c.get("primary_key")]
            for name, table in tables.items()
        }
        assert keys == {"customer": ["id"], "invoice": ["id"]}
        assert [(link["field"], link["to"]) for link in tables["customer"]["links"]] == [
            ("id", {"table": "invoice", "field": "customer_id"})
        ]

    @pytest.mark.skipif(
        "source_type" not in run_shape._PLAN_COLUMN_FIELDS,
        reason="the installed octopize-avatar-yaml does not write a column's source type yet",
    )
    def test_it_carries_each_column_s_source_type(self) -> None:
        runner, _ = _runner(SchemaPlan.from_proposal(_proposal()))

        types = {
            (table["name"], column["field"]): column.get("source_type")
            for table in _schema(runner)["spec"]["tables"]
            for column in table["columns"]
        }

        assert types == {
            ("customer", "id"): "bigint",
            ("customer", "age"): "integer",
            ("invoice", "id"): "bigint",
            ("invoice", "customer_id"): "bigint",
            ("invoice", "total"): "double",
        }


REFUSAL: dict[str, Any] = {"contract_findings": [], "schema_drift": [_drift("new_table", "audit")]}


class TestRefusedExtraction:
    """The Extraction refuses a source that changed since the launch, and files why."""

    def _refused(self, monkeypatch: pytest.MonkeyPatch, filed: bool = True) -> Runner:
        runner, _ = _runner(
            SchemaPlan.from_proposal(_proposal(contract_findings=[], schema_drift=[]))
        )
        runner.run()
        fake = cast("FakeApiClient", runner.client)
        extraction = runner.jobs.get_job_id("extract")
        for name in runner.jobs.get_launched_jobs():
            job_id = runner.jobs.get_job_id(name)
            failed = job_id == extraction
            fake.jobs._jobs[job_id] = fake.jobs._jobs[job_id].model_copy(
                update={
                    "status": JobStatus.error if failed else JobStatus.parent_error,
                    "exception": "the source has schema drift" if failed else "parent failed",
                    "done": True,
                }
            )

        def get_results(job_name: str) -> dict[str, list[str]]:
            if job_name == extraction and filed:
                return {"extraction_refusal": ["fakeurl/extraction_refusal.json"]}
            raise ApiResponseError("Error status 404", response=httpx.Response(404))

        monkeypatch.setattr(fake.results, "get_results", get_results)
        monkeypatch.setattr(runner.file_downloader, "download_file", lambda url: REFUSAL)
        return runner

    def test_waiting_on_the_run_raises_with_the_items_it_filed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = self._refused(monkeypatch)

        with pytest.raises(ExtractionRefusedError) as raised:
            runner.get_all_results()

        assert "the source has schema drift" in str(raised.value)
        assert raised.value.schema_drift == [
            SchemaDriftItem.model_validate(_drift("new_table", "audit"))
        ]
        assert raised.value.contract_findings == []
        assert runner.extraction_refusal() == ExtractionRefusal(
            schema_drift=raised.value.schema_drift
        )

    def test_a_job_that_filed_nothing_fails_as_before(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = self._refused(monkeypatch, filed=False)

        with pytest.raises(ValueError, match="failed with exception") as raised:
            runner.get_all_results()

        assert not isinstance(raised.value, ExtractionRefusedError)
        assert runner.extraction_refusal() is None
