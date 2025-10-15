import re
from pathlib import Path
from typing import Any, TypeGuard

import pandas as pd
from IPython.display import HTML
from pydantic import BaseModel

from avatars.constants import (
    RESULTS_TO_STORE,
    PlotKind,
    Results,
    TypeResults,
    mapping_result_to_file_name,
)
from avatars.models import JobKind


class ResultsOrganizer(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    shuffled: dict[str, pd.DataFrame] = {}
    sensitive_unshuffled: dict[str, pd.DataFrame] = {}
    privacy_metrics: dict[str, list[dict[str, Any]]] = {}
    signal_metrics: dict[str, list[dict[str, Any]]] = {}
    original_projections: dict[str, pd.DataFrame] = {}
    avatars_projections: dict[str, pd.DataFrame] = {}
    figures: dict[str, dict[str, list[HTML]]] = {}
    advice: dict[str, dict[str, Any]] = {}
    run_metadata: dict[JobKind, Any] = {}

    def get_results(self, table_name: str, result_name: Results, job_name: JobKind) -> TypeResults:
        table_name = self.unescape_table_name(table_name)
        match result_name:
            case Results.SHUFFLED:
                return self.shuffled.get(table_name)
            case Results.UNSHUFFLED:
                return self.sensitive_unshuffled.get(table_name)
            case Results.PRIVACY_METRICS:
                return self.privacy_metrics.get(table_name)
            case Results.SIGNAL_METRICS:
                return self.signal_metrics.get(table_name)
            case Results.PROJECTIONS_ORIGINAL:
                return self.original_projections.get(table_name)
            case Results.PROJECTIONS_AVATARS:
                return self.avatars_projections.get(table_name)
            case Results.FIGURES:
                return self.figures.get(table_name)
            case Results.ADVICE:
                return self.advice.get(table_name, {})
            case Results.METADATA:
                return self.run_metadata.get(job_name, {})
            case _:
                raise ValueError(f"Expected result_name to be one of {RESULTS_TO_STORE}")

    def set_results(
        self,
        result_name: Results,
        result: TypeResults,
        table_name: str,
        metadata: dict[str, Any] | None = None,
    ):
        table_name = self.unescape_table_name(table_name)
        match result_name:
            case Results.SHUFFLED:
                if self._is_dataframe(result):
                    self.shuffled[table_name] = result
            case Results.UNSHUFFLED:
                if self._is_dataframe(result):
                    self.sensitive_unshuffled[table_name] = result
            case Results.PRIVACY_METRICS:
                if self._is_list_of_dict(result):
                    self.privacy_metrics.setdefault(table_name, [])
                    self.privacy_metrics[table_name].append(result[0])
            case Results.SIGNAL_METRICS:
                if self._is_list_of_dict(result):
                    self.signal_metrics.setdefault(table_name, [])
                    self.signal_metrics[table_name].append(result[0])
            case Results.PROJECTIONS_ORIGINAL:
                if self._is_dataframe(result):
                    self.original_projections[table_name] = result
            case Results.PROJECTIONS_AVATARS:
                if self._is_dataframe(result):
                    self.avatars_projections[table_name] = result
            case Results.FIGURES:
                if self._is_html(result) and metadata is not None:
                    self.figures.setdefault(table_name, {})
                    if metadata["kind"] in PlotKind:
                        self.figures[table_name].setdefault(PlotKind(metadata["kind"]), []).append(
                            result
                        )
            case Results.ADVICE:
                if isinstance(result, list):
                    for item in result:
                        if item["table_name"] == table_name:
                            self.advice[table_name] = item["advice"]
                            break
            case Results.METADATA:
                if isinstance(result, dict) and metadata is not None:
                    self.run_metadata[metadata["kind"]] = result
            case _:
                raise ValueError(f"Expected result_name to be one of {RESULTS_TO_STORE}")

    def _is_dataframe(self, result: TypeResults) -> TypeGuard[pd.DataFrame]:
        """Validate that the result is a DataFrame."""
        if not isinstance(result, pd.DataFrame):
            raise ValueError("Expected result to be a DataFrame")
        return True

    def _is_list_of_dict(self, result: TypeResults) -> TypeGuard[list[dict[str, Any]]]:
        """Validate that the result is a list of dict."""
        if not isinstance(result, list) or not all(isinstance(r, dict) for r in result):
            raise ValueError("Expected result to be a list of dicts")
        return True

    def _is_html(self, result: TypeResults) -> TypeGuard[HTML]:
        """Validate that the result is HTML."""
        if not isinstance(result, HTML):
            raise ValueError("Expected result to be an HTML object for FIGURES")
        return True

    def get_table_name(
        self,
        result_name: Results,
        url: str,
        result: TypeResults,
        metadata: TypeResults | None = None,
    ) -> str | None:
        """Get the table name from the result based on the result type and URL.
        This method extracts the table name in the URL for tables,
        or from the metadata for other result types."""
        table_name = None
        match result_name:
            case (
                Results.SHUFFLED
                | Results.UNSHUFFLED
                | Results.PROJECTIONS_ORIGINAL
                | Results.PROJECTIONS_AVATARS
            ):
                result_filename = mapping_result_to_file_name[result_name]
                table_name = Path(url).stem.split(f".{result_filename}")[0]
            case Results.SIGNAL_METRICS | Results.PRIVACY_METRICS:
                if isinstance(result, list) and result:
                    table_name = result[0]["metadata"]["table_name"]
                else:
                    raise ValueError(
                        "Expected result to be a list with at least one item for METRICS"
                    )
            case Results.FIGURES:
                if metadata and isinstance(metadata, dict):
                    table_name = metadata.get("table_name", "")
            case Results.ADVICE:
                if isinstance(result, list) and result:
                    table_name = result[0].get("table_name", "")
        return table_name

    def unescape_table_name(self, table_name: str) -> str:
        """Encode the table name to be used in URLs."""
        reversed_replacements = {
            "_dot_": ".",
            "_slash_": "/",
            "_ampersand_": "&",
            "_plus_": "+",
        }
        pattern = re.compile("|".join(re.escape(k) for k in reversed_replacements.keys()))
        return pattern.sub(lambda match: reversed_replacements[match.group(0)], table_name)

    def find_figure_metadata(
        self, figures_metadatas: list[dict[str, Any]], url: str
    ) -> dict[str, Any] | None:
        for metadata in figures_metadatas:
            if metadata.get("filename") == Path(url).name:
                figure_metadata = metadata
                return figure_metadata
        return None
