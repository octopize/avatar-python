"""Each column's treatment reaching the run, not just the plan.

Four treatments a reviewer chooses between -- anonymize, pseudonymize, freeze,
drop -- and each one has to turn into something the engine acts on. None of them
happens by itself: every column of every table is streamed onto storage
whatever the plan says, because the sink writes the table's whole column list.
So a decision that is not carried across is not a decision, it is a value in the
copy.

That is not hypothetical. The per-column pseudonymization strategies were being
dropped exactly here, and a live run put six of eight source addresses in the
target while its plan said to replace them -- because anonymization *resamples*,
drawing from the column's real distribution.
"""

from __future__ import annotations

from typing import Any

import pytest

from avatars.manager import Manager
from avatars.runner import Runner
from avatars.schema_plan import KeyColumnError, SchemaPlan
from tests.unit.conftest import FakeApiClient


def _runner() -> Runner:
    return Manager(api_client=FakeApiClient()).create_runner("crm")


def _reviewed() -> SchemaPlan:
    """One table, one column of each treatment."""
    return SchemaPlan(
        [
            {
                "name": "customer",
                "treatment": "pseudonymize",
                "individual_level": True,
                "cluster": "cluster-1",
                "primary_key": ["id"],
                "columns": [
                    {"name": "id", "action": "keep"},
                    {"name": "age", "action": "anonymize"},
                    {
                        "name": "email",
                        "action": "pseudonymize",
                        "strategy": {"kind": "FAKER", "pii_type": "EMAIL"},
                    },
                    {"name": "currency", "action": "freeze"},
                    {"name": "internal_note", "action": "ignore"},
                ],
            }
        ]
    )


def _planned(**kwargs: Any) -> Runner:
    runner = _runner()
    plan = _reviewed()
    runner.add_database(source="crm_prod", target="crm_test", plan=plan)
    runner.set_parameters("customer", k=5, **kwargs)
    return runner


def _table(runner: Runner) -> Any:
    return runner.config.tables["customer"]


def _excluded(runner: Runner) -> list[str]:
    """The columns the avatarization is told to leave alone."""
    declared = runner.config.avatarization["customer"].exclude_variables or {}
    return sorted(declared.get("variable_names", []))


# --- each treatment lands somewhere ----------------------------------------- #


def test_a_pseudonymized_column_reaches_the_schema() -> None:
    columns = {c.field: c for c in (_table(_planned()).columns or [])}

    assert columns["email"].pseudonymization is not None


def test_a_frozen_column_is_excluded_from_the_avatarization() -> None:
    """Excluding a column is how a run says "leave these values as they are".

    Without this the column is avatarized like any other and the run reports
    success with the decision simply absent from the result.
    """
    runner = _planned()

    assert _excluded(runner) == ["currency"]
    # Row order, which is the only replacement strategy multi-table uses for now.
    declared = runner.config.avatarization["customer"].exclude_variables or {}
    assert declared["replacement_strategy"] == "row_order"


def test_a_dropped_column_is_declared_as_one() -> None:
    """A column nobody wants in the copy is a column nothing should model."""
    dropped = [c.field for c in (_table(_planned()).columns or []) if c.drop]

    assert dropped == ["internal_note"]


def test_an_anonymized_column_is_left_to_the_avatarization() -> None:
    """Which is the whole point of the distinction: nothing claims it.

    A column asked to be anonymized needs no declaration -- the avatarization
    handles it -- so the property to assert is that neither replacement,
    exclusion nor dropping took it.
    """
    runner = _planned()
    columns = {c.field: c for c in (_table(runner).columns or [])}

    # Not declared at all: an anonymized column with no type to state needs no
    # entry, and the engine reads it from the data.
    assert "age" not in columns
    assert "age" not in _excluded(runner)


# --- and the caller is not overruled ---------------------------------------- #


def test_a_column_the_caller_excluded_is_kept() -> None:
    """Somebody excluding a column for their own reasons should not lose it by
    also reviewing a plan.
    """
    runner = _planned(exclude_variable_names=["age"])

    assert _excluded(runner) == ["age", "currency"]


def test_the_plan_reports_what_it_froze_and_dropped() -> None:
    plan = _reviewed()

    assert plan.frozen_columns("customer") == ["currency"]
    assert plan.dropped_columns("customer") == ["internal_note"]


def test_a_table_no_plan_mentions_freezes_nothing() -> None:
    """Asked per configured table, and a table belongs to one plan, not all."""
    assert _reviewed().frozen_columns("nowhere") == []


def test_the_avatarization_still_has_something_to_do() -> None:
    """`anonymizable_columns` decides how a link to a parent can be made, and
    it has to count the columns asked to be anonymized -- the advisor no longer
    leaves ordinary columns at `keep`.
    """
    assert _reviewed().anonymizable_columns("customer") == ["age"]


# --- copying a table means freezing it, except its keys --------------------- #


def _lookup_and_child() -> SchemaPlan:
    """A copied child of an anonymized parent, and a lookup with one label."""
    return SchemaPlan(
        [
            {
                "name": "country",
                "treatment": "copy",
                "cluster": "cluster-1",
                "primary_key": ["code"],
                "columns": [
                    {"name": "code", "action": "keep"},
                    {"name": "name", "action": "keep"},
                ],
            },
            {
                "name": "customer",
                "treatment": "copy",
                "individual_level": True,
                "cluster": "cluster-1",
                "primary_key": ["id"],
                "links": [
                    {
                        "column": "country_code",
                        "references_table": "country",
                        "references_column": "code",
                    }
                ],
                "columns": [
                    {"name": "id", "action": "keep"},
                    {"name": "country_code", "action": "keep"},
                    {"name": "label", "action": "keep"},
                    {"name": "age", "action": "anonymize"},
                ],
            },
        ]
    )


def test_copying_a_table_freezes_every_column_except_its_keys() -> None:
    """Which is what `copy` has to mean, and did not.

    It was read nowhere when a job ran, so a copied table was avatarized like
    any other -- its rows synthesised under a name promising the opposite.
    """
    plan = _lookup_and_child()

    # `label` has no decision of its own, so the table's treatment settles it.
    # `age` was explicitly anonymized, and the more specific decision wins --
    # freezing it too would silently overrule the reviewer.
    assert plan.frozen_columns("customer") == ["label"]
    # The keys are not frozen: a copied child still has to join to a parent
    # whose keys have moved, so the link machinery rewrites them.
    assert "id" not in plan.frozen_columns("customer")
    assert "country_code" not in plan.frozen_columns("customer")


def test_the_keys_of_a_copied_table_are_named_as_keys() -> None:
    plan = _lookup_and_child()

    assert plan.key_columns("customer") == {"id", "country_code"}
    assert plan.non_key_columns("customer") == ["label", "age"]


def test_a_table_nobody_gave_a_treatment_is_anonymized_not_copied() -> None:
    """The default read `copy` while copy behaved as anonymization, so it is now
    the treatment the old default actually performed -- and a plan built by hand
    is not silently shipped verbatim.
    """
    plan = SchemaPlan().for_tables("customer")

    assert plan.treatment_of("customer") == "anonymize"
    assert plan.frozen_columns("customer") == []


# --- a key is the join, not data -------------------------------------------- #


def test_freezing_a_key_is_refused() -> None:
    """It says "keep `country_code = FR`" while FR's row became somebody else."""
    plan = _lookup_and_child()

    with pytest.raises(KeyColumnError, match="country_code"):
        plan.freeze_columns("customer", "country_code")


def test_anonymizing_or_dropping_a_key_is_refused_too() -> None:
    plan = _lookup_and_child()

    with pytest.raises(KeyColumnError):
        plan.anonymize_columns("customer", "id")
    with pytest.raises(KeyColumnError):
        plan.drop_columns("customer", "id")


def test_the_refusal_says_what_to_do_instead() -> None:
    plan = _lookup_and_child()

    with pytest.raises(KeyColumnError) as raised:
        plan.freeze_columns("customer", "id")

    assert "customer.id" in str(raised.value)
    assert "treat the whole table" in str(raised.value)


def test_a_non_key_column_is_still_the_reviewer_s_to_choose() -> None:
    plan = _lookup_and_child()

    plan.freeze_columns("customer", "label")

    assert "label" in plan.frozen_columns("customer")


# --- and the run says so before it starts ----------------------------------- #


def test_a_copied_table_with_nothing_left_to_model_is_refused_early() -> None:
    """The engine refuses it too, from three layers down and without a name:
    "Expected at least one column to be left after excluding variables".
    """
    runner = _runner()
    runner.add_database(source="crm_prod", target="crm_test", plan=_lookup_and_child())

    with pytest.raises(ValueError, match="nothing to work on"):
        runner.set_parameters("country", k=5)


def test_the_refusal_names_the_table_and_both_ways_out() -> None:
    runner = _runner()
    runner.add_database(source="crm_prod", target="crm_test", plan=_lookup_and_child())

    with pytest.raises(ValueError, match="'country'") as raised:
        runner.set_parameters("country", k=5)

    assert "'country'" in str(raised.value)
    assert "anonymize one column" in str(raised.value)
    assert "ignore" in str(raised.value)


def test_a_copied_table_with_something_left_to_model_is_fine() -> None:
    """`customer` is copied but keeps one anonymized column, so the
    avatarization has work and the link machinery has its keys.
    """
    runner = _runner()
    runner.add_database(source="crm_prod", target="crm_test", plan=_lookup_and_child())

    runner.set_parameters("customer", k=5)

    excluded = runner.config.avatarization["customer"].exclude_variables or {}
    assert sorted(excluded.get("variable_names", [])) == ["label"]
