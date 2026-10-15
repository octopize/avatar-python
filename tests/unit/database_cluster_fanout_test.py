"""A database run is one run per group of related tables.

ADR-0008 point 5: "a database job is split into one multi-table job per PK/FK
cluster", so N avatarization jobs contribute to one target database. It is not
a preference. The engine builds a metagraph over a schema's tables and requires
it connected, so a real schema -- several unrelated groups of tables in one
database -- cannot be one avatarization:

    Expected a connected graph, but found 4 disconnected components

and turning that check off does not help, because the engine then refuses to
run anything but an advice job on a schema whose links it did not verify.

Until this, the client said so and stopped. Now it fans out into **one document
set per group**, each one an ordinary multi-table run: the same documents under
the same names a multi-table run has always emitted, over one group's tables.
So nothing about the shape today's multi-table jobs rely on changes, and every
job kind keeps working per group without being renamed.
"""

from __future__ import annotations

import re
from typing import Any, cast

import pytest
import yaml
from avatar_yaml import Config

from avatars.manager import Manager
from avatars.runner import Runner
from avatars.schema_plan import SchemaPlan, shared_entity
from tests.unit.conftest import FakeApiClient, FakeResources


def _runner(seed: int | None = None) -> Runner:
    return Manager(api_client=FakeApiClient()).create_runner("crm", seed=seed)


def _two_clusters() -> SchemaPlan:
    """Customers with invoices, and an audit log that references nothing."""
    return SchemaPlan(
        [
            {
                "name": "customer",
                "cluster": "cluster-1",
                "individual_level": True,
                "primary_key": ["id"],
                "columns": [{"name": "id", "action": "keep"}, {"name": "age", "action": "keep"}],
            },
            {
                "name": "invoice",
                "cluster": "cluster-1",
                "primary_key": ["id"],
                "links": [
                    {
                        "column": "customer_id",
                        "references_table": "customer",
                        "references_column": "id",
                    }
                ],
                "columns": [
                    {"name": "id", "action": "keep"},
                    {"name": "customer_id", "action": "keep"},
                    {"name": "total", "action": "keep"},
                ],
            },
            {
                "name": "event",
                "cluster": "cluster-2",
                "individual_level": True,
                "primary_key": ["id"],
                "columns": [{"name": "id", "action": "keep"}, {"name": "kind", "action": "keep"}],
            },
        ]
    )


def _planned(seed: int | None = 99, **kwargs: object) -> Runner:
    """A reviewed plan, and `k` for each table the run works on.

    The second is what a caller does after reviewing: the plan says which
    tables the run works on, and each of them needs its avatarization
    parameters like any other table.
    """
    plan = _two_clusters()
    runner = _runner(seed=seed)
    runner.add_database(source="crm_prod", target="crm_test", plan=plan, **kwargs)  # type: ignore[arg-type]
    for table in plan.participating():
        runner.set_parameters(table, k=5)
    return runner


def _documents(runner: Runner, cluster: str) -> list[dict[str, Any]]:
    """The documents of one group's set, as the engine will read them."""
    return [doc for doc in yaml.safe_load_all(runner.cluster_yamls()[cluster]) if doc]


def _of_kind(runner: Runner, cluster: str, kind: str) -> list[dict[str, Any]]:
    return [doc for doc in _documents(runner, cluster) if doc.get("kind") == kind]


def _tables_of(runner: Runner, cluster: str) -> list[str]:
    """The tables this group's set runs, read back the way the engine scopes them."""
    return list(Config.from_yaml(runner.cluster_yamls()[cluster]).tables)


def _schema_tables(runner: Runner, cluster: str) -> dict[str, dict[str, Any]]:
    """Every table this set's schema describes -- the whole run's (ADR-0012)."""
    schema = next(
        doc
        for doc in _of_kind(runner, cluster, "AvatarSchema")
        if not doc["spec"].get("schema_ref")
    )
    return {table["name"]: table for table in schema["spec"]["tables"]}


# --- how many runs, and what each one holds ---------------------------------- #


def test_a_plan_covering_two_groups_is_two_document_sets() -> None:
    """It used to be a `ValueError` naming the groups and stopping."""
    assert sorted(_planned().cluster_yamls()) == ["cluster-1", "cluster-2"]


def test_each_set_is_an_ordinary_multi_table_configuration() -> None:
    """The point of one set per group rather than one set holding several.

    Same documents under the same names a multi-table run has always emitted,
    so nothing downstream has to know a database run fanned out -- and every
    job kind keeps working per group.
    """
    for cluster in _planned().cluster_yamls():
        named = {
            (doc["kind"], doc["metadata"]["name"])
            for doc in _documents(_planned(), cluster)
            if doc.get("metadata")
        }
        assert ("AvatarSchema", "schema") in named
        assert ("AvatarSchema", "schema_avatarized") in named
        assert ("AvatarParameters", "standard") in named


def test_no_two_documents_in_a_set_share_a_name() -> None:
    """What one set holding several schemas kept getting wrong.

    Every per-group document had to be renamed after its group, and each one
    left on its default name was emitted twice under one name -- refused by
    the database rather than by anything that could explain it: "duplicate key
    value violates unique constraint uq_resources_name_kind_set_name_user_id".
    One set per group has no such problem to solve.
    """
    runner = _planned()
    for cluster in runner.cluster_yamls():
        identified = [
            (doc["kind"], doc["metadata"]["name"])
            for doc in _documents(runner, cluster)
            if doc.get("metadata")
        ]
        duplicated = {item for item in identified if identified.count(item) > 1}
        assert not duplicated, f"{cluster}: emitted twice under one name: {sorted(duplicated)}"


def test_a_group_holds_its_own_tables_and_no_others() -> None:
    """The whole point: each set runs a connected graph of its own.

    Its schema describes the whole database (ADR-0012) and its Extraction's `group` says which
    part of it this set runs -- the engine keeps exactly those tables, as reading it back does.
    """
    runner = _planned()

    assert sorted(_tables_of(runner, "cluster-1")) == ["customer", "invoice"]
    assert _tables_of(runner, "cluster-2") == ["event"]
    assert sorted(_schema_tables(runner, "cluster-2")) == ["customer", "event", "invoice"]


def test_the_link_inside_a_group_is_still_declared() -> None:
    """A group is closed under foreign keys, so no link crosses out of it.

    Which is why the fan-out needs no link surgery -- and why the links that do
    belong to a group have to survive the split, or the engine sees two
    unrelated tables again.
    """
    schema = next(
        doc
        for doc in _of_kind(_planned(), "cluster-1", "AvatarSchema")
        if not doc["spec"].get("schema_ref")
    )
    parent = next(t for t in schema["spec"]["tables"] if t["name"] == "customer")

    assert parent["links"], "the link between customer and invoice was dropped"
    assert parent["links"][0]["to"]["table"] == "invoice"


def test_a_group_declares_each_link_once() -> None:
    """A projection already carries the links; re-declaring them appended.

    `create_link` appends to the parent's list, so building each group's tables
    again on top of the copy gave `customer` two identical links -- a different
    schema, not a tidier one.
    """
    schema = next(
        doc
        for doc in _of_kind(_planned(), "cluster-1", "AvatarSchema")
        if not doc["spec"].get("schema_ref")
    )
    parent = next(t for t in schema["spec"]["tables"] if t["name"] == "customer")

    assert len(parent["links"]) == 1


def test_each_run_only_works_on_its_own_tables() -> None:
    """Each set's Extraction says which group it runs, and every table its group.

    The other groups' tables keep their real treatment -- the engine plans them `ignore` for
    this set (ADR-0012) -- so one set is enough to read the whole run back. The former shape
    wrote that `ignore` into each set's plan, which lost what the reviewer had decided.
    """
    runner = _planned()
    for cluster in runner.cluster_yamls():
        (extraction,) = _of_kind(runner, cluster, "AvatarExtractParameters")
        assert extraction["spec"]["group"] == cluster
        assert extraction["spec"]["source"] == "crm_prod"
        parameters = next(doc for doc in _of_kind(runner, cluster, "AvatarParameters"))
        assert "input" not in parameters["spec"], "each job names its database now"

    tables = _schema_tables(runner, "cluster-2")
    assert {name: table.get("group") for name, table in tables.items()} == {
        "customer": "cluster-1",
        "invoice": "cluster-1",
        "event": "cluster-2",
    }
    assert "ignore" not in {table.get("treatment") for table in tables.values()}


def test_there_is_no_single_configuration_to_ask_for() -> None:
    """`get_yaml` would have to name one group and imply it is the whole run."""
    runner = _planned()

    with pytest.raises(ValueError, match="2 document sets"):
        runner.get_yaml()


# --- one run each ----------------------------------------------------------- #


def test_running_it_creates_one_set_per_group() -> None:
    runner = _planned()

    runner.run()

    sets = runner.cluster_sets()
    assert sorted(sets) == ["cluster-1", "cluster-2"]
    assert len(set(sets.values())) == 2, "the groups share a set"


def test_every_group_runs_the_jobs_a_run_normally_runs() -> None:
    """Nothing is a special kind, so metrics and the report work per group."""
    runner = _planned()

    runner.run()

    statuses = runner.statuses()
    assert "cluster-1/standard" in statuses
    assert "cluster-2/standard" in statuses
    assert all(str(status) == "finished" for status in statuses.values())


def test_every_group_writes_its_target_in_its_own_generation_job() -> None:
    """ADR-0011: per group, its Extraction, its avatarization, then its Génération."""
    runner = _planned()

    runner.run()

    for cluster in ("cluster-1", "cluster-2"):
        kinds = [key.split("/")[1] for key in runner.statuses() if key.startswith(cluster)]
        assert kinds[:3] == ["extract", "standard", "regenerate"], kinds


def test_the_groups_do_not_depend_on_each_other() -> None:
    """Two groups share no table, so neither ordering nor a fan-in is needed to
    keep the target's referential integrity -- and one failing should leave the
    others' work standing.
    """
    runner = _planned()

    runner.run()

    assert sorted(runner.clusters()) == ["cluster-1", "cluster-2"]
    assert runner.clusters()["cluster-2"] == ["event"]


# --- one identity per person, across the runs ------------------------------- #


def test_a_fanned_out_run_is_seeded_so_its_jobs_agree_about_people() -> None:
    """A shared entity's replacement follows the order entities are collected, and
    each job resolves the reference tables for itself. `seed` is what makes
    them agree; the engine's default_factory would give each parameters
    document a fresh one.
    """
    runner = _planned(
        seed=None,
        shared_entities=[shared_entity("rt", tables=["customer"], key="id", replace=["email"])],
    )

    assert runner.config.seed is not None
    seeds = {
        doc["spec"]["seed"]
        for cluster in runner.cluster_yamls()
        for doc in _of_kind(runner, cluster, "AvatarParameters")
    }
    assert len(seeds) == 1, "the groups would resolve different people"


def test_a_seed_somebody_chose_is_kept() -> None:
    runner = _planned(seed=1234)

    assert runner.config.seed == 1234
    assert {
        doc["spec"]["seed"]
        for cluster in runner.cluster_yamls()
        for doc in _of_kind(runner, cluster, "AvatarParameters")
    } == {1234}


def test_every_group_gets_the_whole_shared_entity_declaration() -> None:
    """Collection has to range over every table the entity names, whatever
    group it is in -- otherwise the entity *set* differs per run and one seed
    is not enough to make them agree.
    """
    runner = _planned(
        shared_entities=[
            shared_entity("rt", tables=["customer", "event"], key="id", replace=["email"])
        ]
    )

    for cluster in runner.cluster_yamls():
        (rt,) = _of_kind(runner, cluster, "AvatarSharedEntity")
        assert rt["metadata"]["name"] == "rt"
        assert {place["table"] for place in rt["spec"]["key"]["mapping"]} == {"customer", "event"}
        assert rt["spec"]["seed"] == 99, "the run's seed: the same person in every group"


# --- and one group is still one ordinary run -------------------------------- #


def test_one_group_of_tables_is_not_a_fan_out() -> None:
    """The ordinary case, unchanged: one set, one `get_yaml`, no groups."""
    runner = _runner()
    plan = SchemaPlan(
        [
            {"name": "customer", "cluster": "cluster-1", "individual_level": True, "columns": []},
            {"name": "invoice", "cluster": "cluster-1", "columns": []},
        ]
    )
    runner.add_database(source="crm_prod", target="crm_test", plan=plan)

    assert set(runner.config.tables) == {"customer", "invoice"}
    assert runner.clusters() == {}
    assert runner.cluster_yamls() == {}
    documents = [doc for doc in yaml.safe_load_all(runner.get_yaml()) if doc]
    assert {"schema", "schema_avatarized"} <= {
        doc["metadata"]["name"] for doc in documents if doc.get("kind") == "AvatarSchema"
    }


def test_each_sets_display_name_is_one_the_api_accepts() -> None:
    """A display name may hold only letters, digits, `_` and `-`.

    Anything else is a 422 -- "Input can only contain letters, numbers, and
    the following special characters: _-" -- so the group cannot be joined on
    with a spaced dash however much better it reads.
    """
    runner = _planned()

    runner.run()

    uploaded = cast("FakeResources", runner.client.resources)._stored_names
    for name in uploaded:
        assert re.fullmatch(r"[A-Za-z0-9_-]+", name), name
    assert any(name.endswith("-cluster-1") for name in uploaded)


def test_a_group_left_without_an_individual_level_table_is_given_one() -> None:
    """Discovery chose one per group as it found them; a plan that splits a group has none.

    The engine refuses such a set -- "does not have any individual_level table defined" --
    so one is chosen, as the web app chooses: personal data first, then a table that
    references nothing in its group.
    """
    plan = _two_clusters()
    plan.set_individual_level("event", False)

    plan.ensure_individual_level()

    assert plan.is_individual_level("event")
    assert plan.is_individual_level("customer"), "a reviewer's choice is kept"
    assert not plan.is_individual_level("invoice")


def test_no_job_starts_when_a_group_s_set_is_refused() -> None:
    """Every set is stored before any job starts: a refusal leaves nothing half-launched."""
    runner = _planned()
    pushed: list[str] = []
    original = runner.client.resources.put_resources

    def refuse_the_second(display_name: str, yaml_string: str) -> object:
        pushed.append(display_name)
        if len(pushed) == 2:
            raise RuntimeError("Schema 'schema' does not have any individual_level table")
        return original(display_name=display_name, yaml_string=yaml_string)

    runner.client.resources.put_resources = refuse_the_second  # type: ignore[method-assign,assignment]

    with pytest.raises(RuntimeError, match="individual_level"):
        runner.run()

    assert len(pushed) == 2
    assert not runner.cluster_sets(), "no group was launched"


# --- the run's reference job (ADR-0013) ------------------------------------ #


def _recording(runner: Runner) -> list[tuple[str, str, list[str]]]:
    """Every job the runner creates: its set, its parameters and what it waits for."""
    created: list[tuple[str, str, list[str]]] = []
    client = cast(FakeApiClient, runner.client)
    send = client.send_request

    def record(method: str, url: str, **kwargs: Any) -> dict[str, str]:
        request = kwargs["json_data"]
        created.append(
            (str(request.set_name), request.parameters_name, list(request.depends_on or []))
        )
        answer: dict[str, str] = send(method, url, **kwargs)  # type: ignore[no-untyped-call]
        return {**answer, "Location": answer["name"]}

    client.send_request = record  # type: ignore[method-assign]
    return created


def _with_entity() -> Runner:
    return _planned(
        shared_entities=[shared_entity("rt", tables=["customer"], key="id", replace=["email"])]
    )


def test_a_run_s_shared_entity_is_resolved_by_a_reference_job_of_its_own() -> None:
    runner = _with_entity()
    created = _recording(runner)

    runner.run()

    resources = cast(FakeResources, cast(FakeApiClient, runner.client).resources)
    [name] = [n for n in resources._stored_names if n.endswith("--reference-tables")]
    assert name.startswith("crm__"), "named like the run's groups, so it is listed with them"
    [(reference_set, _, waits)] = [c for c in created if c[1] == "reference"]
    assert waits == [], "it waits for nothing"
    assert reference_set not in runner.cluster_sets().values(), "a set of its own"
    documents = list(yaml.safe_load_all(resources._stored_resources[reference_set]))
    assert {d["kind"] for d in documents} >= {
        "AvatarReferenceParameters",
        "AvatarSharedEntity",
        "AvatarDatabase",
    }
    assert "reference-tables/reference" in runner.statuses()


def test_every_group_s_extraction_and_generation_wait_for_the_reference_job() -> None:
    runner = _with_entity()
    created = _recording(runner)

    runner.run()

    for set_name in runner.cluster_sets().values():
        waits = {params: deps for s, params, deps in created if s == set_name}
        assert "reference" in waits["extract"]
        assert "reference" in waits["regenerate"]
        assert "reference" not in waits["standard"], "the avatarization reads no source"


def test_a_run_with_no_shared_entity_has_no_reference_job() -> None:
    runner = _planned()
    created = _recording(runner)

    runner.run()

    assert all(params != "reference" for _, params, _ in created)
    assert not any(k.startswith("reference-tables/") for k in runner.statuses())
