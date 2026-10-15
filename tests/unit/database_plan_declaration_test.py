"""Declaring the tables a database run works on.

Nothing declared them. The engine streams each one onto storage when the job
runs, but the configuration is validated when it is *uploaded*, long before
that -- so every database run was refused outright with

    Schema 'schema' does not have any individual_level table defined

which is where the database path stopped, before the protocol ran at all.
"""

from __future__ import annotations

from avatar_yaml.models.schema import LinkMethod

from avatars.manager import Manager
from avatars.runner import Runner
from avatars.schema_plan import SchemaPlan
from tests.unit.conftest import FakeApiClient


def _runner() -> Runner:
    return Manager(api_client=FakeApiClient()).create_runner("crm")


def _reviewed(individual: str = "customer") -> SchemaPlan:
    plan = SchemaPlan().for_tables("customer", "invoice")
    return plan.set_individual_level(individual)


def test_the_planned_tables_are_declared() -> None:
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test", plan=_reviewed())

    assert set(runner.config.tables) == {"customer", "invoice"}


def test_only_the_table_whose_rows_are_people_is_individual_level() -> None:
    """Rows of a customer table are people; rows of an invoice table are not.

    Marking both would not merely be untidy -- it changes what the metrics
    measure.
    """
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test", plan=_reviewed())

    assert runner.config.tables["customer"].individual_level is True
    assert runner.config.tables["invoice"].individual_level is False


def test_a_reviewer_can_correct_what_discovery_proposed() -> None:
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test", plan=_reviewed("invoice"))

    assert runner.config.tables["invoice"].individual_level is True
    assert runner.config.tables["customer"].individual_level is False


def test_the_tables_are_provided_by_the_input_protocol() -> None:
    """No file to name: the engine streams them out of the database.

    Declared `auto`, the same way a documents run declares its extracted
    table, so a dependent job knows a path has to be filled in for it.
    """
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test", plan=_reviewed())

    for table in runner.config.tables.values():
        assert table.data is not None
        assert table.data.auto is True


def test_no_plan_declares_nothing() -> None:
    """The discovery phase: the tables are not known yet, so none are declared."""
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test")

    assert dict(runner.config.tables) == {}


def test_a_table_the_caller_declared_is_left_alone() -> None:
    """Somebody overriding one table should not be overruled by the plan."""
    runner = _runner()
    runner.config.create_table("customer", individual_level=True, provided_by_input=True)

    runner.add_database(source="crm_prod", target="crm_test", plan=_reviewed("invoice"))

    # Their declaration stands, and the rest of the plan still arrives.
    assert runner.config.tables["customer"].individual_level is True
    assert "invoice" in runner.config.tables


def test_an_ignored_table_is_not_declared() -> None:
    """It is not in the output at all, so there is nothing to avatarize.

    Declaring it would ask the run to open a dataset that was never written.
    """
    runner = _runner()
    plan = SchemaPlan().for_tables("customer", "staging_tmp").set_individual_level("customer")

    runner.add_database(source="crm_prod", target="crm_test", plan=plan.ignore("staging_tmp"))

    assert set(runner.config.tables) == {"customer"}


def test_a_purged_table_is_not_declared() -> None:
    """It arrives with no rows, so it has nothing to avatarize either."""
    runner = _runner()
    plan = SchemaPlan().for_tables("customer", "audit_log").set_individual_level("customer")

    runner.add_database(source="crm_prod", target="crm_test", plan=plan.purge("audit_log"))

    assert set(runner.config.tables) == {"customer"}


def test_a_plan_covering_unrelated_groups_is_one_job_per_group() -> None:
    """It used to be refused here.

    The engine builds a metagraph over a schema's tables and requires it
    connected, so several clusters cannot be one schema -- and turning that
    check off does not help: it also stops the avatarization running at all.
    Several clusters means several jobs, which is what ADR-0008 specifies and
    is now what happens. See `database_cluster_fanout_test.py`; what belongs
    here is that the tables are still all declared.
    """
    runner = _runner()
    plan = SchemaPlan(
        [
            {"name": "customer", "columns": [], "cluster": "c1", "individual_level": True},
            {"name": "invoice", "columns": [], "cluster": "c1"},
            {"name": "audit_log", "columns": [], "cluster": "c2", "individual_level": True},
        ]
    )

    runner.add_database(source="crm_prod", target="crm_test", plan=plan)

    assert set(runner.config.tables) == {"customer", "invoice", "audit_log"}


def test_one_cluster_is_accepted() -> None:
    runner = _runner()
    plan = SchemaPlan(
        [
            {"name": "customer", "columns": [], "cluster": "c1", "individual_level": True},
            {"name": "invoice", "columns": [], "cluster": "c1"},
        ]
    )

    runner.add_database(source="crm_prod", target="crm_test", plan=plan)

    assert set(runner.config.tables) == {"customer", "invoice"}


def test_a_hand_built_plan_is_not_second_guessed() -> None:
    """`for_tables(...)` records no clusters, and that is not a claim of isolation.

    Treating each table as its own group would refuse a multi-table plan whose
    links the caller declared themselves.
    """
    runner = _runner()
    plan = SchemaPlan().for_tables("customer", "invoice").set_individual_level("customer")

    runner.add_database(source="crm_prod", target="crm_test", plan=plan)

    assert set(runner.config.tables) == {"customer", "invoice"}


def _with_email_strategy() -> SchemaPlan:
    """A plan as discovery produces one: a column proposed for replacement."""
    return SchemaPlan(
        [
            {
                "name": "customer",
                "treatment": "pseudonymize",
                "individual_level": True,
                "cluster": "c1",
                "columns": [
                    {
                        "name": "email",
                        "action": "pseudonymize",
                        "strategy": {"kind": "FAKER", "pii_type": "EMAIL"},
                    },
                    {"name": "amount", "action": "keep"},
                ],
            }
        ]
    )


def test_a_columns_replacement_strategy_reaches_the_schema() -> None:
    """Without this the plan's central decision is silently dropped.

    The avatarization *resamples* a categorical column -- it draws values from
    the real distribution -- so every real email stays in the copy against a
    different person. A live run put six of eight source addresses in the
    target, two of them twice, while the plan said "pseudonymize
    customer.email".
    """
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test", plan=_with_email_strategy())

    columns = {c.field: c for c in (runner.config.tables["customer"].columns or [])}
    assert columns["email"].pseudonymization is not None


def test_a_column_the_plan_keeps_is_left_to_the_avatarization() -> None:
    """No strategy is declared for it, so the avatarization handles it.

    Which for a quantity is right: an amount should be synthetic, not a real
    amount belonging to somebody else. A kept column with no declared type is
    not in the schema's column list at all -- the engine reads it from the data
    -- so the property to assert is that nothing claimed it.
    """
    runner = _runner()

    runner.add_database(source="crm_prod", target="crm_test", plan=_with_email_strategy())

    replaced = {
        c.field for c in (runner.config.tables["customer"].columns or []) if c.pseudonymization
    }
    assert replaced == {"email"}


def test_the_plan_reports_which_columns_are_replaced() -> None:
    plan = _with_email_strategy()

    assert set(plan.pseudonymized_columns("customer")) == {"email"}


def test_every_link_uses_the_order_preserving_method_for_now() -> None:
    """Row order for every multi-table link while the database path is built.

    A decision, not a discovered constraint -- but it is also the only method
    that works from a parent the avatarization leaves nothing to do. The
    assignment methods compare *synthesised* parent rows, and a lookup table
    whose only real column is pseudonymized has none: "parent table 'country'
    has no anonymizable columns. Only 'SENSITIVE_ORIGINAL_ORDER_ASSIGNMENT' is
    allowed". That is `country` in the sample database exactly.

    The trade-off is recorded on the enum member: keeping the original order to
    assign a child to its parent is a privacy breach. So this test pins a "for
    now", and it is the place to change when a method is chosen per link.
    """
    plan = SchemaPlan(
        [
            {
                "name": "country",
                "cluster": "c1",
                "primary_key": ["code"],
                "columns": [
                    {"name": "code", "action": "keep"},
                    {
                        "name": "name",
                        "action": "pseudonymize",
                        "strategy": {"kind": "FAKER", "pii_type": "FULL_NAME"},
                    },
                ],
            },
            {
                "name": "customer",
                "cluster": "c1",
                "individual_level": True,
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
                    {"name": "age", "action": "keep"},
                ],
            },
        ]
    )

    assert plan.anonymizable_columns("country") == []
    # customer has something to avatarize, and gets the same method anyway.
    assert plan.anonymizable_columns("customer") == ["age"]

    runner = _runner()
    runner.add_database(source="crm_prod", target="crm_test", plan=plan)

    links = runner.config.tables["country"].links or []
    assert links, "the link was not declared"
    assert links[0].method == LinkMethod.SENSITIVE_ORIGINAL_ORDER_ASSIGNMENT


def _a_link_table() -> SchemaPlan:
    """Chinook's `playlist_track`, as the SQLite file declares it.

    Keyed on both of its columns -- `PRIMARY KEY (PlaylistId, TrackId)` -- and
    each of them a foreign key. The same table in the PostgreSQL sample has no
    primary key at all, which is why only the SQLite copy was refused.
    """
    keyed = {"primary_key": ["id"], "columns": [{"name": "id", "action": "keep"}]}
    return SchemaPlan(
        [
            {"name": "playlist", "cluster": "c1", "individual_level": True, **keyed},
            {"name": "track", "cluster": "c1", **keyed},
            {
                "name": "playlist_track",
                "cluster": "c1",
                "primary_key": ["playlist_id", "track_id"],
                "links": [
                    {
                        "column": "playlist_id",
                        "references_table": "playlist",
                        "references_column": "id",
                    },
                    {"column": "track_id", "references_table": "track", "references_column": "id"},
                ],
                "columns": [
                    {"name": "playlist_id", "action": "keep"},
                    {"name": "track_id", "action": "keep"},
                ],
            },
        ]
    )


def test_a_link_table_keyed_on_its_foreign_keys_is_declared() -> None:
    """No single column of a composite key is a key, so none is declared one.

    It was its first column, which is also a foreign key, and a column cannot be
    both: "Expected a primary_key and foreign_keys to be different fields". Every
    database with a many-to-many table was refused before it ran -- Chinook's
    `playlist_track` and Northwind's `CustomerCustomerDemo` among the demos.
    """
    runner = _runner()

    runner.add_database(source="chinook", target="chinook_test", plan=_a_link_table())

    columns = runner.config.tables["playlist_track"].columns or []
    assert not any(column.primary_key for column in columns)
    assert sorted(column.field for column in columns if column.identifier) == [
        "playlist_id",
        "track_id",
    ]


def test_both_of_a_link_tables_links_are_kept() -> None:
    """The point of declaring them foreign keys: the target keeps its joins."""
    runner = _runner()

    runner.add_database(source="chinook", target="chinook_test", plan=_a_link_table())

    children = {
        (parent, link.to.table, link.to.field)
        for parent, table in runner.config.tables.items()
        for link in table.links or []
    }
    assert ("playlist", "playlist_track", "playlist_id") in children
    assert ("track", "playlist_track", "track_id") in children


def test_a_table_that_references_itself_declares_no_link_to_itself() -> None:
    """`employees.ReportsTo` names another employee, in Chinook and Northwind alike.

    A link from a table to itself is a cycle in the metagraph, and the whole set
    was refused on upload: "Expected the relationship between tables to be
    acyclic, got a cycle instead". The column stays a key -- its values are
    still what the constraint in the target checks -- as the web app does.
    """
    plan = SchemaPlan(
        [
            {
                "name": "employee",
                "cluster": "c1",
                "individual_level": True,
                "primary_key": ["id"],
                "links": [
                    {
                        "column": "reports_to",
                        "references_table": "employee",
                        "references_column": "id",
                    }
                ],
                "columns": [
                    {"name": "id", "action": "keep"},
                    {"name": "reports_to", "action": "keep"},
                ],
            }
        ]
    )
    runner = _runner()

    runner.add_database(source="chinook", target="chinook_test", plan=plan)

    employee = runner.config.tables["employee"]
    assert not employee.links
    assert [column.field for column in employee.columns or [] if column.identifier] == [
        "reports_to"
    ]


def test_a_column_asked_to_arrive_empty_is_not_modelled() -> None:
    """Northwind's `Employees.Photo`, a binary column discovery purges by default.

    It was declared like any other column, so the avatarization left it out of
    the avatars -- there is nothing to model in it -- while every job reading them
    afterwards expected it: "Column info contains columns not present in table:
    ['Photo']", for the Génération and both metrics alike. Declared dropped, as
    the web app does; the write-back still creates it, empty.
    """
    plan = SchemaPlan(
        [
            {
                "name": "employee",
                "cluster": "c1",
                "individual_level": True,
                "primary_key": ["id"],
                "columns": [
                    {"name": "id", "action": "keep"},
                    {"name": "age", "action": "anonymize"},
                    {"name": "photo", "action": "purge"},
                ],
            }
        ]
    )
    runner = _runner()

    runner.add_database(source="northwind", target="northwind_test", plan=plan)

    assert plan.emptied_columns("employee") == ["photo"]
    dropped = [c.field for c in runner.config.tables["employee"].columns or [] if c.drop]
    assert dropped == ["photo"]
