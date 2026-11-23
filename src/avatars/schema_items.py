"""The contract findings and the schema drift of a database run, as structured items.

An item of a kind this client does not know is kept as it came: it still holds the run.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError

from avatars.job_polling import JobFailedError

CONTRACT_FINDINGS = "contract_findings"
SCHEMA_DRIFT = "schema_drift"


class FindingKind(StrEnum):
    missing_table = "missing_table"
    missing_column = "missing_column"
    type_mismatch = "type_mismatch"
    unreadable_type = "unreadable_type"
    unchecked_type = "unchecked_type"


class SchemaDriftKind(StrEnum):
    new_table = "new_table"
    new_column = "new_column"
    missing_table = "missing_table"
    missing_column = "missing_column"
    changed_type = "changed_type"


class ContractFindingItem(BaseModel):
    """One thing a data contract names that the source does not have, or has with another type."""

    kind: FindingKind
    table: str
    column: str | None = None
    contract_type: str | None = None
    discovered_type: str | None = None
    # English, never naming a value.
    message: str


class SchemaDriftItem(BaseModel):
    """One difference between the discovered schema and the approved schema of a database run."""

    kind: SchemaDriftKind
    table: str
    column: str | None = None
    # For ``changed_type`` only.
    approved_type: str | None = None
    discovered_type: str | None = None
    # English, never naming a value.
    message: str


def items_of[Item: (ContractFindingItem, SchemaDriftItem)](
    model: type[Item], value: Any
) -> list[Item]:
    """Each item of *value*, as *model*. One of a kind this client does not know is kept as it
    came: it still holds the run.
    """
    items: list[Item] = []
    for entry in value if isinstance(value, list) else []:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(model.model_validate(entry))
        except ValidationError:
            items.append(model.model_construct(**entry))
    return items


class ExtractionRefusal(BaseModel):
    """Why an Extraction refused its source, as its job filed it."""

    contract_findings: list[ContractFindingItem] = []
    schema_drift: list[SchemaDriftItem] = []

    @classmethod
    def from_result(cls, value: Any) -> ExtractionRefusal:
        """Read the ``extraction_refusal`` result of a job, tolerating any shape."""
        record = value if isinstance(value, dict) else {}
        return cls.model_construct(
            contract_findings=items_of(ContractFindingItem, record.get(CONTRACT_FINDINGS)),
            schema_drift=items_of(SchemaDriftItem, record.get(SCHEMA_DRIFT)),
        )


class ExtractionRefusedError(JobFailedError):
    """Raised when a run's Extraction refused its source: a contract finding or schema drift.

    :attr:`contract_findings` and :attr:`schema_drift` hold each item the Extraction filed.
    """

    def __init__(self, failed: JobFailedError, refusal: ExtractionRefusal) -> None:
        super().__init__(str(failed), job_name=failed.job_name, job=failed.job)
        self.contract_findings = list(refusal.contract_findings)
        self.schema_drift = list(refusal.schema_drift)
