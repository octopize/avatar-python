"""Reviewing what happens to each table and column, without writing configuration.

The engine's plan is a nested document: treatments, actions, strategies,
provenance flags. A caller should never type one. Discovery proposes it,
and this is what a person reviews it with -- verbs, not keys:

    plan = (
        runner.proposed_plan()
        .confirm_all()
        .reject("customer", "city")
        .purge("audit_log")
        .ignore("staging_tmp")
        .continue_sequence("customer", "customer_id")
    )
    runner.set_plan(plan)

Every method returns the plan, so a review reads as a sentence. Nothing here
touches YAML, and `to_dict` -- the one method that produces the engine's shape
-- is for the `Runner` to call, not for you.

Names are chosen for what the user is deciding, not for what the engine calls
it: `purge` says "keep the table, drop the rows", `ignore` says "leave it out
altogether", and `reject` says "the machine was wrong about this column".
"""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from avatar_yaml import PiiType, PseudonymizationStrategy

# What the engine calls things. Confined to this module on purpose: a caller
# should not have to learn the vocabulary to review a plan.
_TREATMENT = "treatment"
_COLUMNS = "columns"
_ACTION = "action"
_STRATEGY = "strategy"
_PROVENANCE = "provenance"
_REVIEWED = "reviewed"
_SUGGESTED_BY = "suggested_by"
_SEQUENCE = "sequence"
_SEQUENCE_START = "sequence_start"


class UnknownTableError(ValueError):
    """Raised when a review names a table the plan does not contain."""


class UnknownColumnError(ValueError):
    """Raised when a review names a column the table does not contain."""


class KeyColumnError(ValueError):
    """Raised when a review asks for a treatment on a primary or foreign key."""


class Proposal:
    """One column a classifier had an opinion about."""

    def __init__(self, table: str, column: dict[str, Any]) -> None:
        self._table = table
        self._column = column

    @property
    def table(self) -> str:
        return self._table

    @property
    def column(self) -> str:
        return str(self._column["name"])

    @property
    def pii_type(self) -> str | None:
        """What the classifier thinks the column holds, e.g. ``"EMAIL"``."""
        value = self._column.get("pii_type")
        return None if value is None else str(value)

    @property
    def suggested_by(self) -> str | None:
        """``"rules"`` or ``"model"``.

        Worth reading before anything else. A name rule is deterministic and
        can be confirmed in bulk; a model guess deserves a look.
        """
        provenance = self._column.get(_PROVENANCE) or {}
        value = provenance.get(_SUGGESTED_BY)
        return None if value is None else str(value)

    @property
    def confidence(self) -> float | None:
        """How sure the classifier was, when it reports one."""
        provenance = self._column.get(_PROVENANCE) or {}
        value = provenance.get("confidence")
        return None if value is None else float(value)

    @property
    def reviewed(self) -> bool:
        provenance = self._column.get(_PROVENANCE) or {}
        return bool(provenance.get(_REVIEWED, False))

    def __repr__(self) -> str:
        sure = "" if self.confidence is None else f", confidence {self.confidence}"
        return (
            f"{self.table}.{self.column}: {self.pii_type} "
            f"(by {self.suggested_by}{sure}, "
            f"{'reviewed' if self.reviewed else 'NOT reviewed'})"
        )


class SchemaPlan:
    """What happens to each table and column, ready to be reviewed.

    Get one from `Runner.proposed_plan()`, review it, and hand it back with
    `Runner.set_plan()`. It is refused by the server while anything a machine
    proposed is unconfirmed, which is the point of it existing.
    """

    def __init__(self, tables: list[dict[str, Any]] | None = None) -> None:
        self._tables: list[dict[str, Any]] = tables if tables is not None else []

    # -- getting one -------------------------------------------------------- #

    @classmethod
    def from_proposal(cls, proposal: dict[str, Any]) -> SchemaPlan:
        """Wrap what discovery proposed."""
        tables = proposal.get("tables") or []
        return cls([dict(table) for table in tables])

    def for_tables(self, *names: str) -> SchemaPlan:
        """Start a plan from scratch, for callers not using discovery."""
        for name in names:
            self._tables.append({"name": name, _COLUMNS: []})
        return self

    # -- reading it --------------------------------------------------------- #

    @property
    def tables(self) -> list[str]:
        return [str(table["name"]) for table in self._tables]

    def is_individual_level(self, table: str) -> bool:
        """Whether one row of *table* is one person.

        Discovery proposes this from the shape of the links -- a table nothing
        points at holds individuals, one hanging off it does not -- and you can
        correct it with :meth:`set_individual_level`. The run needs it: a
        schema with no individual-level table is refused, and marking the wrong
        one changes what the metrics mean rather than merely failing.
        """
        for entry in self._tables:
            if entry.get("name") == table:
                return bool(entry.get("individual_level", False))
        return False

    def set_individual_level(self, table: str, value: bool = True) -> SchemaPlan:
        """Say whether one row of *table* is one person, overriding discovery."""
        for entry in self._tables:
            if entry.get("name") == table:
                entry["individual_level"] = value
        return self

    def ensure_individual_level(self) -> SchemaPlan:
        """Make sure each group of related tables has a table whose rows are people.

        The engine refuses a schema with none -- "does not have any individual_level table
        defined, expected at least one" -- and each group is a schema of its own. Discovery
        proposes one per group as it found them, which stops being enough when a plan changes
        anything: skip the table it chose, or split a group, and a group has none.

        Chosen as the web app chooses (`ensureIndividualLevel`): the most columns holding
        personal data, then a table that references no other table of its group, then the
        name. Marks, never unmarks -- a reviewer's choice is not second-guessed.
        """
        for tables in self.clustered().values():
            if any(self.is_individual_level(name) for name in tables):
                continue
            chosen = min(tables, key=lambda name: self._individual_rank(name, set(tables)))
            self.set_individual_level(chosen)
        return self

    def _individual_rank(self, name: str, group: set[str]) -> tuple[int, bool, str]:
        """How likely *name* is to hold people: personal data first, then a parent, then name."""
        personal = sum(
            1
            for column in self._table_of(name).get(_COLUMNS) or []
            if str(column.get(_ACTION, "keep")) in {"pseudonymize", "reference"}
        )
        child = any(link["references_table"] in group for link in self.links(name))
        return (-personal, child, name)

    def individual_level_tables(self) -> list[str]:
        """Every table whose rows are people."""
        return [name for name in self.tables if self.is_individual_level(name)]

    def column_types(self, table: str) -> dict[str, str]:
        """What each column of *table* holds, as the source declared it.

        Facts, not decisions: discovery reads them off the database and they
        travel on the plan because the plan is what reaches the run. Declaring
        them is what stops the types being inferred from the file the table was
        streamed to -- a date column arrives as text and the avatarization dies
        on `ufunc 'subtract' cannot use operands with types dtype('O')`.
        """
        found: dict[str, str] = {}
        for column in self._table_of(table).get(_COLUMNS) or []:
            declared = column.get("column_type")
            if declared:
                found[str(column["name"])] = str(declared)
        return found

    def pseudonymized_columns(self, table: str) -> dict[str, Any]:
        """Which of *table*'s columns are replaced, and with what.

        Declared on the schema, because the alternative is to let the
        avatarization handle them -- and avatarization *resamples*: it draws a
        categorical column's values from the real distribution, so every real
        email is still in the copy, merely against a different person. A live
        run showed exactly that: six of eight source addresses present in the
        target, two of them twice.

        Pseudonymization replaces a value with a fake one. For an email, a
        phone number or a name that is the only acceptable answer, which is why
        the classifier proposes it and why the choice is per column rather than
        per table.
        """
        found: dict[str, Any] = {}
        for column in self._table_of(table).get(_COLUMNS) or []:
            if column.get(_ACTION) != "pseudonymize":
                continue
            strategy = column.get(_STRATEGY)
            if strategy is not None:
                found[str(column["name"])] = strategy
        return found

    def anonymizable_columns(self, table: str) -> list[str]:
        """*table*'s columns the avatarization still has something to do with.

        Both the columns asked to be anonymized and the ones left to the
        table's treatment, minus the keys. Everything else is handled before
        the avatarization sees it -- a pseudonymized column is replaced, a
        frozen one is excluded, a purged or ignored one is not there -- and a
        key is carried rather than synthesised. So a table whose every
        remaining column is one of those has nothing to avatarize.

        Which decides how a link to it can be made: the engine allows only
        `SENSITIVE_ORIGINAL_ORDER_ASSIGNMENT` from such a parent, because the
        others assign children by comparing synthesised parent rows and there
        are none to compare.
        """
        entry = self._table_of(table)
        primary = self.primary_key(table)
        foreign = {link["column"] for link in self.links(table)}
        return [
            str(column["name"])
            for column in entry.get(_COLUMNS) or []
            if str(column.get(_ACTION, "keep")) in {"keep", "anonymize"}
            and str(column["name"]) != primary
            and str(column["name"]) not in foreign
        ]

    def frozen_columns(self, table: str) -> list[str]:
        """*table*'s columns kept verbatim, excluded from the avatarization.

        "Excluded from the avatarization" is how a run says "leave these values
        exactly as they are", so this is what the decision turns into. Without
        being carried across, a frozen column is avatarized like any other and
        the run reports success with the decision simply absent from the
        result.

        **Every non-key column, for a table set to copy.** That treatment calls
        itself "carried across unchanged" and was read nowhere when a job ran,
        so a copied table was avatarized like any other -- its rows synthesised
        under a name promising the opposite. Freezing its columns is what copy
        has to mean.

        The keys are deliberately not included. A copied child still has to
        join to its parent, and if that parent was anonymized its keys have
        moved -- so the keys must be rewritten by the link machinery, exactly as
        for any other treatment. That is the "except foreign keys" in "copied
        as-is, except foreign keys".

        An unknown table yields nothing rather than raising: a run copying
        several databases asks this per configured table, and a table belongs
        to one of the plans, not all of them.
        """
        frozen = self._columns_with(table, "freeze")
        if self.treatment_of(table) != "copy":
            return frozen
        # Only the columns with no decision of their own. `KEEP` means "the
        # table's treatment settles it", and for a copied table that is
        # verbatim -- while a column explicitly set to anonymize or
        # pseudonymize has been spoken about, and the more specific decision
        # wins. Freezing those too would silently overrule the reviewer.
        undecided = set(self._columns_with(table, "keep"))
        return list(
            dict.fromkeys([*frozen, *(c for c in self.non_key_columns(table) if c in undecided)])
        )

    def treatment_of(self, table: str) -> str:
        """What happens to *table*'s rows. Avatarized unless something says otherwise.

        Not ``"copy"``, which is what this read while copying was honoured
        nowhere and therefore behaved as avatarization. Now that copying keeps
        every value verbatim, defaulting to it would ship a table's real rows
        because nobody had an opinion about it.
        """
        try:
            return str(self._table_of(table).get(_TREATMENT, "anonymize"))
        except UnknownTableError:
            return ""

    def non_key_columns(self, table: str) -> list[str]:
        """*table*'s columns that are neither its primary key nor a foreign key.

        The keys are what the link machinery owns, and everything else is what a
        treatment can speak about.
        """
        try:
            entry = self._table_of(table)
        except UnknownTableError:
            return []
        keys = self.key_columns(table)
        return [
            str(column["name"])
            for column in entry.get(_COLUMNS) or []
            if str(column["name"]) not in keys
        ]

    def key_columns(self, table: str) -> set[str]:
        """*table*'s primary key and foreign keys, as discovery read them."""
        primary = self._table_of(table).get("primary_key")
        keys = {str(name) for name in primary} if isinstance(primary, list) else set()
        return keys | {link["column"] for link in self.links(table)}

    def dropped_columns(self, table: str) -> list[str]:
        """*table*'s columns that are absent from the output altogether.

        Dropped before the avatarization rather than after: a column nobody
        wants in the copy is also a column nothing should model, and the
        engine's `columns_to_drop` is where a schema says so.
        """
        return self._columns_with(table, "ignore")

    def emptied_columns(self, table: str) -> list[str]:
        """*table*'s columns that arrive in the copy present and empty.

        A binary column is one by default: there is nothing in a photo to
        model. Not modelled either -- the avatarization leaves it out of the
        avatars, and the write-back creates it empty in the target.
        """
        return self._columns_with(table, "purge")

    def _refuse_keys(self, table: str, columns: tuple[str, ...], action: str) -> None:
        """A key's values belong to the link machinery, not to a treatment.

        Freezing a foreign key says "keep `customer_id = 42`" while the
        parent's 42 has become a different synthetic person -- a silently broken
        join, which is the one thing a test database exists to exercise.
        Anonymizing or pseudonymizing a key is the same category error.

        So it is refused rather than quietly ignored: a copy that looks
        complete and joins to the wrong people is worse than a copy that would
        not start.
        """
        keys = self.key_columns(table)
        named = sorted(set(columns) & keys)
        if not named:
            return
        raise KeyColumnError(
            f"{', '.join(f'{table}.{name}' for name in named)} "
            f"{'is a key' if len(named) == 1 else 'are keys'}, so it cannot be "
            f"{action}d -- the link between a parent and its children is what keeps "
            "them joinable, and rewriting a key is the engine's to do. Leave it alone, "
            "or treat the whole table."
        )

    def _columns_with(self, table: str, action: str) -> list[str]:
        try:
            entry = self._table_of(table)
        except UnknownTableError:
            return []
        return [
            str(column["name"])
            for column in entry.get(_COLUMNS) or []
            if str(column.get(_ACTION, "keep")) == action
        ]

    def primary_key(self, table: str) -> str | None:
        """*table*'s primary key, as discovery read it.

        Declared because a link is only declarable between a declared primary
        key and a declared foreign key, or the configuration is refused with
        "Expected field `id` to be the primary key of the table `customer`".
        The foreign keys come from :meth:`links`, which also says what each one
        points at.

        A composite primary key yields none. The engine's schema takes one
        field, and no single column of a composite key is a key -- in a link
        table (`PRIMARY KEY (playlist_id, track_id)`) each of them is a foreign
        key, which a column cannot also be. A child needs no primary key of its
        own (#6771), and the web app declares a composite key the same way.
        """
        primary = self._table_of(table).get("primary_key")
        if isinstance(primary, list) and len(primary) == 1:
            return str(primary[0])
        return None

    def links(self, table: str) -> list[dict[str, str]]:
        """The foreign keys *table* declares, as discovery read them.

        Needed because the run has to declare them: the engine builds a
        metagraph over a schema's tables and requires it connected, so a
        cluster whose links are not declared looks like a pile of unrelated
        tables -- "Expected a connected graph, but found 3 disconnected
        components", for three tables that plainly reference each other.
        """
        found = self._table_of(table).get("links")
        if not isinstance(found, list):
            return []
        return [
            {
                "column": str(link["column"]),
                "references_table": str(link["references_table"]),
                "references_column": str(link["references_column"]),
            }
            for link in found
            if isinstance(link, dict) and link.get("references_table")
        ]

    def clusters(self) -> list[list[str]]:
        """The participating tables, grouped into connected components.

        Discovery computes these from the foreign keys and records the cluster
        each table belongs to. One cluster is one avatarization job: tables
        that reference each other have to be anonymized together, and tables
        that do not are separate datasets that happen to live in the same
        database.
        """
        # A plan built by hand -- `for_tables(...)` -- says nothing about
        # clusters. Treating each table as its own would refuse a multi-table
        # plan whose links the caller declared themselves, which is a
        # legitimate thing to do and none of this function's business.
        return list(self.clustered().values())

    def clustered(self) -> dict[str, list[str]]:
        """Cluster name -> its participating tables, in a stable order.

        The named form of :meth:`clusters`, because a run needs the name: one
        cluster is one avatarization job, and the job, its schema and its
        results are all identified by it.

        Discovery records the name on each table, named after the table the
        most links touch (``group-customer``), so a job list says which tables
        a run covers. A plan built by hand records none, and every table is
        taken to belong to the same group -- see :meth:`clusters` for why
        treating them as isolated would be wrong.
        """
        participating = self.participating()
        if not participating:
            return {}
        recorded = {name: str(self._table_of(name).get("cluster") or "") for name in participating}
        if not any(recorded.values()):
            return {"group-1": participating}

        groups: dict[str, list[str]] = {}
        for name in participating:
            groups.setdefault(recorded[name] or name, []).append(name)
        return dict(sorted(groups.items()))

    def for_cluster(self, cluster: str) -> SchemaPlan:
        """This plan, scoped to one cluster. The other tables are ignored.

        A copy: every review method on this class mutates in place and returns
        ``self``, so scoping without copying would quietly reduce the
        reviewer's plan to one cluster.

        **Ignored**, not purged. A purged table still reaches the output -- with
        no rows -- so the job would demand it in the target and check that it is
        empty, and one cluster job would then refuse the target its sibling had
        already written into. An ignored table is not in this job at all, which
        is what belonging to another cluster means.
        """
        known = self.clustered()
        if cluster not in known:
            raise UnknownTableError(
                f"this plan has no cluster {cluster!r}; it has: {', '.join(known) or 'none'}"
            )
        keep = set(known[cluster])
        scoped = SchemaPlan(deepcopy(self._tables))
        elsewhere = [name for name in scoped.tables if name not in keep]
        return scoped.ignore(*elsewhere) if elsewhere else scoped

    def copy_of(self) -> SchemaPlan:
        """An independent copy, for reviewing one way without disturbing another.

        Every review method here mutates in place and returns ``self``, which
        reads well and means "the same plan, treated differently" needs saying
        explicitly.
        """
        return SchemaPlan(deepcopy(self._tables))

    def qualified_by(self, copy: str) -> SchemaPlan:
        """This plan with every table name prefixed by the database it is in.

        For a run copying several databases. Two of them both holding
        ``customer`` are two tables, and the protocol stages them as
        ``crm.customer`` and ``billing.customer`` -- so a configuration
        declaring either as ``customer`` describes neither, and the run is
        refused for having no table it can find.

        The links are requalified too: a foreign key names the table it points
        at, and a copy's key points inside that same copy -- no foreign key
        crosses a database.
        """
        qualified = SchemaPlan(deepcopy(self._tables))
        for table in qualified._tables:
            table["name"] = qualified_table(copy, str(table["name"]))
            for link in table.get("links") or []:
                if isinstance(link, dict) and link.get("references_table"):
                    link["references_table"] = qualified_table(copy, str(link["references_table"]))
        return qualified

    def participating(self) -> list[str]:
        """The tables the run actually works on.

        An **ignored** table is not in the output at all and a **purged** one
        arrives with no rows, so neither has anything to avatarize -- and
        declaring them would ask the run to open a dataset that was never
        written. This is the list to declare tables from; :attr:`tables` is
        every table the plan mentions, including the ones it excludes.
        """
        excluded = {"ignore", "purge"}
        return [
            str(entry["name"])
            for entry in self._tables
            if str(entry.get(_TREATMENT, "anonymize")) not in excluded
        ]

    def proposals(self, table: str | None = None) -> list[Proposal]:
        """Every column a classifier had an opinion about, reviewed or not."""
        found: list[Proposal] = []
        for entry in self._tables:
            if table is not None and entry["name"] != table:
                continue
            for column in entry.get(_COLUMNS) or []:
                if (column.get(_PROVENANCE) or {}).get(_SUGGESTED_BY):
                    found.append(Proposal(str(entry["name"]), column))
        return found

    def needs_review(self) -> dict[str, list[str]]:
        """Table -> the columns still waiting on a decision.

        Empty means the plan will be accepted. Anything else is what the server
        will refuse the job for, named so you can go and look.
        """
        waiting: dict[str, list[str]] = {}
        for proposal in self.proposals():
            if not proposal.reviewed:
                waiting.setdefault(proposal.table, []).append(proposal.column)
        return {table: sorted(columns) for table, columns in waiting.items()}

    def is_reviewed(self) -> bool:
        return not self.needs_review()

    def summary(self) -> str:
        """One line: what will happen, and what is still unanswered."""
        counts: dict[str, int] = {}
        for table in self._tables:
            counts[str(table.get(_TREATMENT, "copy"))] = (
                counts.get(str(table.get(_TREATMENT, "copy")), 0) + 1
            )
        described = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
        waiting = sum(len(columns) for columns in self.needs_review().values())
        return f"{described}; {waiting} column(s) awaiting review"

    # -- reviewing it ------------------------------------------------------- #

    def confirm(self, table: str, *columns: str) -> SchemaPlan:
        """Agree with the classifier about these columns."""
        for column in self._columns_of(table, columns):
            column.setdefault(_PROVENANCE, {})[_REVIEWED] = True
        return self

    def confirm_all(self) -> SchemaPlan:
        """Agree with every proposal.

        A real decision, not a shortcut: it records that a person accepted each
        of them. Read `proposals()` first — the ones `suggested_by` a model are
        the ones worth reading individually.
        """
        for proposal in self.proposals():
            self.confirm(proposal.table, proposal.column)
        return self

    def reject(self, table: str, *columns: str) -> SchemaPlan:
        """Disagree: leave these columns exactly as they are.

        Recorded as a decision, which is not the same as never having looked.

        **Frozen**, which is what "exactly as they are" means. It used to
        record `keep`, and `keep` leaves the column to the table's treatment --
        so a rejected column was avatarized, and avatarization *resamples*.
        "This estate needs real cities" produced a column of real cities drawn
        from the real distribution and attached to different people, which is
        neither what was asked for nor obviously wrong from the outside.
        """
        for column in self._columns_of(table, columns):
            column[_ACTION] = "freeze"
            column.pop(_STRATEGY, None)
            column.pop("pii_type", None)
            column.setdefault(_PROVENANCE, {})[_REVIEWED] = True
        return self

    def replace(self, table: str, column: str, strategy: PseudonymizationStrategy) -> SchemaPlan:
        """Say how a column should be replaced, when you disagree with the strategy."""
        entry = self._column_of(table, column)
        entry[_ACTION] = "pseudonymize"
        entry[_STRATEGY] = strategy
        entry.setdefault(_PROVENANCE, {})[_REVIEWED] = True
        return self

    def freeze_columns(self, table: str, *columns: str) -> SchemaPlan:
        """Keep these columns' values exactly as they are.

        Excluded from the avatarization rather than passed through it. For a
        column whose exact values a consumer depends on and which identifies
        nobody: a currency code, a status, a product reference.

        Not something a classifier proposes -- whether a consumer depends on a
        column's values is not answerable from a schema and a type.
        """
        return self._treat_columns(table, columns, "freeze")

    def anonymize_columns(self, table: str, *columns: str) -> SchemaPlan:
        """Avatarize these columns: a synthetic value from the real distribution.

        Right for a quantity, and wrong for an identifier -- resampling means
        real values do survive into the output, against different people. Use
        :meth:`replace` for anything personal.
        """
        return self._treat_columns(table, columns, "anonymize")

    def drop_columns(self, table: str, *columns: str) -> SchemaPlan:
        """Leave these columns out of the copy altogether.

        Not emptied -- not there. A consumer cannot tell the column ever
        existed, which is the difference from emptying it.
        """
        return self._treat_columns(table, columns, "ignore")

    def _treat_columns(self, table: str, columns: tuple[str, ...], action: str) -> SchemaPlan:
        """Record a decision about columns, and mark it as one.

        Reviewed, because choosing a treatment *is* the review -- leaving it
        pending would ask a person to confirm their own answer.
        """
        self._refuse_keys(table, columns, action)
        for column in self._columns_of(table, columns):
            column[_ACTION] = action
            column.pop(_STRATEGY, None)
            column.pop("pii_type", None)
            column.setdefault(_PROVENANCE, {})[_REVIEWED] = True
        return self

    # -- deciding what a classifier cannot ---------------------------------- #

    def copy(self, *tables: str) -> SchemaPlan:
        """Take these tables as they are."""
        return self._treat(tables, "copy")

    def pseudonymize(self, *tables: str) -> SchemaPlan:
        """Keep the rows and the joins, replace the personal values."""
        return self._treat(tables, "pseudonymize")

    def anonymize(self, *tables: str) -> SchemaPlan:
        """Avatarize these tables."""
        return self._treat(tables, "anonymize")

    def purge(self, *tables: str) -> SchemaPlan:
        """Keep the table, drop every row. For an audit log."""
        return self._treat(tables, "purge")

    def ignore(self, *tables: str) -> SchemaPlan:
        """Leave these out of the copy altogether."""
        return self._treat(tables, "ignore")

    # -- generated columns -------------------------------------------------- #

    def continue_sequence(self, table: str, column: str) -> SchemaPlan:
        """Carry on numbering after the rows just copied.

        What a copied `SERIAL` column needs. Without it the sequence is still
        at 1 while the data holds ids in the thousands, and the first insert
        your application makes collides.
        """
        self._column_of(table, column)[_SEQUENCE] = "to_max"
        return self

    def restart_sequence(self, table: str, column: str) -> SchemaPlan:
        """Start numbering again from the beginning. For a purged table."""
        self._column_of(table, column)[_SEQUENCE] = "restart"
        return self

    def start_sequence_at(self, table: str, column: str, value: int) -> SchemaPlan:
        """Number from *value* on.

        Useful deliberately above the copied range: start at 1 000 000 and
        every row your tests create is visibly their own.
        """
        entry = self._column_of(table, column)
        entry[_SEQUENCE] = "start_at"
        entry[_SEQUENCE_START] = value
        return self

    # -- what the Runner needs ---------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        """The engine's shape. For `Runner`, not for you."""
        return {"tables": [dict(table) for table in self._tables]}

    def __iter__(self) -> Iterator[str]:
        return iter(self.tables)

    def __repr__(self) -> str:
        return f"SchemaPlan({self.summary()})"

    # -- internals ---------------------------------------------------------- #

    def _table_of(self, name: str) -> dict[str, Any]:
        for table in self._tables:
            if table["name"] == name:
                return table
        raise UnknownTableError(
            f"this plan has no table {name!r}; it has: {', '.join(self.tables) or 'none'}"
        )

    def _column_of(self, table: str, column: str) -> dict[str, Any]:
        entry = self._table_of(table)
        columns = entry.setdefault(_COLUMNS, [])
        for existing in columns:
            if existing["name"] == column:
                return existing  # type: ignore[no-any-return]
        known = ", ".join(str(c["name"]) for c in columns)
        raise UnknownColumnError(
            f"table {table!r} has no column {column!r}; it has: {known or 'none'}"
        )

    def _columns_of(self, table: str, columns: tuple[str, ...]) -> list[dict[str, Any]]:
        if columns:
            return [self._column_of(table, column) for column in columns]
        # No names given: every column of that table a classifier proposed.
        return [
            column
            for column in self._table_of(table).get(_COLUMNS) or []
            if (column.get(_PROVENANCE) or {}).get(_SUGGESTED_BY)
        ]

    def _treat(self, tables: tuple[str, ...], treatment: str) -> SchemaPlan:
        for name in tables:
            entry = self._table_of(name)
            entry[_TREATMENT] = treatment
            if treatment in _UNTREATED:
                _make_inert(entry)
        return self


_UNTREATED = frozenset({"copy", "purge", "ignore"})
"""Treatments under which a column replacement would never happen."""


def _make_inert(table: dict[str, Any]) -> None:
    """Drop column replacements from a table nothing will treat.

    The engine refuses the combination outright -- "table 'audit_log' is set to
    ignore but plans actor_email for replacement" -- and it is right to: a plan
    saying a column will be replaced, on a table that is not in the output, is
    a plan that means two different things.

    It is this side's job to prevent, though. Confirming a classifier's
    proposals and *then* ignoring a table is an ordinary way to review a plan,
    and it should leave a coherent plan behind rather than one the server
    rejects.
    """
    for column in table.get(_COLUMNS) or []:
        column[_ACTION] = "keep"
        column.pop(_STRATEGY, None)


def shared_entity(
    name: str,
    *,
    replace: list[str],
    across: dict[str, tuple[str, str]] | None = None,
    tables: list[str] | None = None,
    key: str | None = None,
    strategy: PseudonymizationStrategy | None = None,
) -> SharedEntity:
    """Declare something several tables or databases share: one replacement everywhere.

    A person, a product, a site, a configuration code -- anything found under a key
    in more than one table. It gets one replacement wherever it appears, which is
    what keeps the joins in a test estate meaningful. Written as an
    ``AvatarSharedEntity`` (ADR-0012); it was a reference table.

    Within one database, name the tables and the column that identifies it::

        shared_entity("rt_person", tables=["customer", "order"], key="customer_id",
                replace=["email"])

    Across databases the column is usually spelled differently in each, so name
    it per database::

        shared_entity("rt_person",
                across={"crm": ("customer", "person_id"),
                        "billing": ("invoice", "customer_ref")},
                replace=["email"])

    Parameters
    ----------
    name
        A label for this entity, e.g. ``"rt_person"``.
    replace
        The attributes to replace once per person, e.g. ``["email", "phone"]``.
    across
        Database -> (table, the column identifying the person there).
    tables, key
        The single-database form: the tables, and the column they share.
    strategy
        How to replace each attribute. Defaults to realistic fake data of the
        matching kind.

    """
    if (across is None) == (tables is None):
        raise ValueError(
            "declare either 'across' (several databases) or 'tables' with 'key' "
            "(one database), not both and not neither"
        )

    if across is not None:
        join_key = key or next(iter(across.values()))[1]  # across is not None here
        source_tables: list[Any] = [
            {"source": database, "table": table, "key": column}
            for database, (table, column) in across.items()
        ]
    else:
        if key is None:
            raise ValueError("declare 'key': the column that identifies the person")
        join_key = key
        source_tables = list(tables or [])

    return SharedEntity(
        {
            "name": name,
            "join_key": join_key,
            "source_tables": source_tables,
            "columns": [
                {"name": attribute, "strategy": strategy or _default_strategy(attribute)}
                for attribute in replace
            ],
        }
    )


def _default_strategy(attribute: str) -> PseudonymizationStrategy:
    """Realistic fake data of the kind the attribute's name suggests."""
    from avatar_yaml import FakeDataStrategy  # noqa: PLC0415

    guesses = {
        "email": PiiType.EMAIL,
        "phone": PiiType.PHONE,
        "first_name": PiiType.FIRST_NAME,
        "last_name": PiiType.LAST_NAME,
        "name": PiiType.FULL_NAME,
        "address": PiiType.ADDRESS,
        "ssn": PiiType.SSN,
    }
    lowered = attribute.lower()
    for token, pii_type in guesses.items():
        if token in lowered:
            return FakeDataStrategy(pii_type=pii_type)
    return FakeDataStrategy(pii_type=PiiType.FREE_TEXT)


COPY_QUALIFIER = "."
"""Separates a database's name from a table's, e.g. ``crm.customer``.

A dot because the schema already escapes it (``_dot_``), so two databases both
holding ``customer`` produce two distinct, legal table names. The engine's
`databases` protocol stages them under exactly this form.
"""


def qualified_table(copy: str, table: str) -> str:
    """``crm`` and ``customer`` -> ``crm.customer``."""
    return f"{copy}{COPY_QUALIFIER}{table}"


def connection(name: str) -> dict[str, str]:
    """A named connection, as the configuration expects it.

    A caller passes the name their deployment holds; this is the shape the
    engine wants. `sql` because a database is what this addresses -- a
    directory of extracts is a different thing and not what a user reaches for.
    """
    return {"backing": "sql", "location": name}


MIN_AVATAR_YAML = "0.1.45"
"""The first `octopize-avatar-yaml` carrying `create_input_*` -- 0.1.44 on PyPI does not."""


def config_creator(config: object, name: str) -> Any:
    """The `Config.create_input_*` method *name*, or a clear error saying why not.

    A version probe, deliberately: `octopize-avatar-yaml` is pinned to an exact
    release, so a client can be newer than the library that knows how to write
    the section. Without this the caller gets `AttributeError: 'Config' object
    has no attribute 'create_input_database'`, which says nothing about what to
    install.
    """
    creator = getattr(config, name, None)
    if creator is None:
        raise NotImplementedError(
            f"this feature needs octopize-avatar-yaml >= {MIN_AVATAR_YAML}, which is "
            f"where Config.{name} arrives. Upgrade it, or upgrade this client to a "
            "release that pins it."
        )
    return creator


@dataclass(frozen=True)
class SharedEntity:
    """Something several tables or databases share, replaced the same everywhere.

    Built with :func:`shared_entity`.
    """

    _spec: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """The engine's shape. For `Runner`, not for you."""
        return dict(self._spec)

    def __repr__(self) -> str:
        return f"SharedEntity({self._spec.get('name')!r})"
