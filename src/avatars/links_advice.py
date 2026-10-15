"""The links that an advice job advises between the tables of a schema."""

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from avatar_yaml.models.schema import LinkMethod


@dataclass(frozen=True)
class AdvisedLink:
    """A link from the primary key of a parent table to a foreign key of a child table."""

    parent_table: str
    parent_field: str
    child_table: str
    child_field: str
    method: LinkMethod
    confidence: str
    """``high``: the schema leaves one parent, or the names match. ``medium``: the foreign key
    name contains the parent name. ``low``: a weak name match, or the only top-level candidate.
    """


@dataclass(frozen=True)
class UnlinkedForeignKey:
    """A foreign key that the advisor could not link to one parent table."""

    table: str
    field: str
    candidate_tables: list[str] = dataclasses.field(default_factory=list)
    """The tables that can be its parent. Empty when no table can be."""


@dataclass(frozen=True)
class TablesLinksAdvice:
    """The links advice of a whole schema."""

    links: list[AdvisedLink] = dataclasses.field(default_factory=list)
    unlinked_foreign_keys: list[UnlinkedForeignKey] = dataclasses.field(default_factory=list)


def parse_tables_links_advice(results: Iterable[Any]) -> TablesLinksAdvice:
    """Read the links advice from the advice results of each table.

    An advice result is one ``{"table_name": ..., "advice": {...}}`` entry, or a list of them.
    """
    links: list[AdvisedLink] = []
    unlinked: list[UnlinkedForeignKey] = []
    for result in results:
        entries = result if isinstance(result, list) else [result]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            table_name = entry.get("table_name", "")
            advice = entry.get("advice") or {}
            links.extend(
                AdvisedLink(
                    parent_table=table_name,
                    parent_field=link["field"],
                    child_table=link["to"]["table"],
                    child_field=link["to"]["field"],
                    method=LinkMethod(link["method"]),
                    confidence=link["confidence"],
                )
                for link in advice.get("links") or []
            )
            unlinked.extend(
                UnlinkedForeignKey(
                    table=table_name,
                    field=key["field"],
                    candidate_tables=list(key.get("candidate_tables") or []),
                )
                for key in advice.get("unlinked_foreign_keys") or []
            )
    return TablesLinksAdvice(links=links, unlinked_foreign_keys=unlinked)
