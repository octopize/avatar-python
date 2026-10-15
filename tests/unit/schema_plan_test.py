"""Reviewing a plan without writing configuration.

The point of this surface is that a caller never types `treatment`,
`provenance` or `reviewed`. These tests are about the verbs doing what they
say, and about the plan refusing to look reviewed when it is not.
"""

from __future__ import annotations

from typing import Any

import pytest

from avatars import FakeDataStrategy, PiiType, SchemaPlan, shared_entity
from avatars.schema_plan import UnknownColumnError, UnknownTableError


def proposal() -> dict[str, Any]:
    """What discovery proposes for a small CRM, as the engine produces it."""
    return {
        "tables": [
            {
                "name": "customer",
                "treatment": "pseudonymize",
                "columns": [
                    {"name": "customer_id"},
                    {
                        "name": "email",
                        "action": "pseudonymize",
                        "pii_type": "EMAIL",
                        "strategy": {"pii_type": "EMAIL"},
                        "provenance": {"suggested_by": "rules"},
                    },
                    {
                        "name": "ref_3",
                        "action": "pseudonymize",
                        "pii_type": "SSN",
                        "strategy": {"pii_type": "SSN"},
                        "provenance": {"suggested_by": "model", "confidence": 0.91},
                    },
                    {"name": "city"},
                ],
            },
            {"name": "order", "columns": [{"name": "order_id"}]},
            {"name": "audit_log", "columns": [{"name": "entry_id"}]},
        ]
    }


# --- reading a proposal ----------------------------------------------------- #


def test_a_fresh_proposal_is_not_reviewed() -> None:
    """Which is what stops it being run by accident."""
    plan = SchemaPlan.from_proposal(proposal())

    assert plan.is_reviewed() is False
    assert plan.needs_review() == {"customer": ["email", "ref_3"]}


def test_a_proposal_says_who_proposed_it_and_how_sure() -> None:
    """The field a reviewer should read first: a name rule and a model guess
    do not deserve the same attention.
    """
    by_column = {p.column: p for p in SchemaPlan.from_proposal(proposal()).proposals()}

    assert by_column["email"].suggested_by == "rules"
    assert by_column["email"].confidence is None
    assert by_column["ref_3"].suggested_by == "model"
    assert by_column["ref_3"].confidence == 0.91
    assert by_column["ref_3"].pii_type == "SSN"


def test_a_column_nobody_proposed_is_not_awaiting_review() -> None:
    """`city` carries no provenance, so there is nothing to confirm about it."""
    plan = SchemaPlan.from_proposal(proposal())
    assert "city" not in plan.needs_review()["customer"]


# --- the review verbs ------------------------------------------------------- #


def test_confirming_clears_the_gate() -> None:
    plan = SchemaPlan.from_proposal(proposal()).confirm_all()

    assert plan.is_reviewed() is True
    assert plan.needs_review() == {}


def test_confirming_one_column_leaves_the_others_waiting() -> None:
    plan = SchemaPlan.from_proposal(proposal()).confirm("customer", "email")

    assert plan.needs_review() == {"customer": ["ref_3"]}


def test_rejecting_is_a_decision_not_a_pending_item() -> None:
    """Declining a proposal must not look the same as never having looked."""
    plan = SchemaPlan.from_proposal(proposal()).confirm("customer", "email")
    plan.reject("customer", "ref_3")

    assert plan.is_reviewed() is True
    column = plan.to_dict()["tables"][0]["columns"][2]
    # Frozen, which is what "leave it exactly as it is" means. It recorded
    # `keep`, and `keep` leaves the column to the table's treatment -- so a
    # rejected column was avatarized, and avatarization resamples. "This
    # estate needs real cities" produced real cities against other people.
    assert column["action"] == "freeze"
    assert "strategy" not in column
    assert column["provenance"]["reviewed"] is True


def test_replacing_the_strategy_also_counts_as_reviewed() -> None:
    plan = SchemaPlan.from_proposal(proposal()).confirm_all()
    plan.replace("customer", "email", FakeDataStrategy(pii_type=PiiType.FREE_TEXT))

    column = plan.to_dict()["tables"][0]["columns"][1]
    assert column["action"] == "pseudonymize"
    assert column["strategy"].pii_type == PiiType.FREE_TEXT


# --- decisions a classifier cannot make ------------------------------------- #


def test_treatments_read_as_what_they_do() -> None:
    plan = SchemaPlan.from_proposal(proposal())
    plan.purge("audit_log").ignore("order")

    tables = {t["name"]: t.get("treatment") for t in plan.to_dict()["tables"]}
    assert tables == {
        "customer": "pseudonymize",
        "order": "ignore",
        "audit_log": "purge",
    }


def test_a_review_reads_as_one_sentence() -> None:
    """The whole reason this exists rather than a dict."""
    plan = (
        SchemaPlan.from_proposal(proposal())
        .confirm_all()
        .reject("customer", "ref_3")
        .purge("audit_log")
        .continue_sequence("customer", "customer_id")
    )

    assert plan.is_reviewed() is True
    assert "purge" in plan.summary()


# --- generated columns ------------------------------------------------------ #


def test_continuing_a_sequence() -> None:
    plan = SchemaPlan.from_proposal(proposal()).continue_sequence("customer", "customer_id")
    assert plan.to_dict()["tables"][0]["columns"][0]["sequence"] == "to_max"


def test_starting_a_sequence_above_the_copied_range() -> None:
    plan = SchemaPlan.from_proposal(proposal())
    plan.start_sequence_at("customer", "customer_id", 1_000_000)

    column = plan.to_dict()["tables"][0]["columns"][0]
    assert (column["sequence"], column["sequence_start"]) == ("start_at", 1_000_000)


# --- mistakes are named ----------------------------------------------------- #


def test_a_misspelt_table_says_what_there_is() -> None:
    with pytest.raises(UnknownTableError, match="customer, order, audit_log|audit_log"):
        SchemaPlan.from_proposal(proposal()).purge("audit_logs")


def test_a_misspelt_column_says_what_there_is() -> None:
    with pytest.raises(UnknownColumnError, match="email"):
        SchemaPlan.from_proposal(proposal()).confirm("customer", "e_mail")


# --- shared entities -------------------------------------------------------- #


def test_one_database_names_the_tables_and_the_shared_key() -> None:
    declared = shared_entity(
        "rt_person", tables=["customer", "order"], key="customer_id", replace=["email"]
    ).to_dict()

    assert declared["join_key"] == "customer_id"
    assert declared["source_tables"] == ["customer", "order"]
    assert declared["columns"][0]["name"] == "email"


def test_several_databases_name_the_key_per_database() -> None:
    """The same person is `person_id` in one and `customer_ref` in the other."""
    declared = shared_entity(
        "rt_person",
        across={"crm": ("customer", "person_id"), "billing": ("invoice", "customer_ref")},
        replace=["email"],
    ).to_dict()

    assert declared["source_tables"] == [
        {"source": "crm", "table": "customer", "key": "person_id"},
        {"source": "billing", "table": "invoice", "key": "customer_ref"},
    ]


def test_the_strategy_is_guessed_from_the_attribute_name() -> None:
    """So the common case needs no strategy argument at all."""
    declared = shared_entity(
        "rt", tables=["t"], key="id", replace=["email", "last_name"]
    ).to_dict()

    kinds = [column["strategy"].pii_type for column in declared["columns"]]
    assert kinds == [PiiType.EMAIL, PiiType.LAST_NAME]


def test_declaring_neither_form_is_refused() -> None:
    with pytest.raises(ValueError, match="either 'across'"):
        shared_entity("rt", replace=["email"])


def test_declaring_both_forms_is_refused() -> None:
    with pytest.raises(ValueError, match="not both"):
        shared_entity("rt", tables=["t"], key="id", across={"a": ("t", "id")}, replace=["email"])
