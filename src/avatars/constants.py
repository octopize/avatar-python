import io
import re
from enum import StrEnum
from typing import (
    IO,
    Any,
    BinaryIO,
    Union,
)

import pandas as pd
from avatar_yaml.models.schema import ColumnType
from IPython.display import HTML

from avatars.models import JobKind

DEFAULT_TIMEOUT = 5

FileLike = Union[BinaryIO, IO[Any], io.IOBase]
FileLikes = list[FileLike]
VOLUME_NAME = "input"

JOB_EXECUTION_ORDER = [
    JobKind.standard,
    JobKind.signal_metrics,
    JobKind.privacy_metrics,
    JobKind.report,
]

ERROR_STATUSES = ["parent_error", "error"]

READY_STATUSES = ["finished", *ERROR_STATUSES]

DEFAULT_RETRY_INTERVAL = 5


class Results(StrEnum):
    ADVICE = "advice"
    SHUFFLED = "shuffled"
    UNSHUFFLED = "unshuffled"
    PRIVACY_METRICS = "privacy_metrics"
    SIGNAL_METRICS = "signal_metrics"
    REPORT_IMAGES = "report_images"
    PROJECTIONS_ORIGINAL = "original_projections"
    PROJECTIONS_AVATARS = "avatar_projections"
    METADATA = "run_metadata"
    REPORT = "report"
    META_PRIVACY_METRIC = "meta_privacy_metric"
    META_SIGNAL_METRIC = "meta_signal_metric"
    FIGURES = "figures"
    FIGURES_METADATA = "figures_metadata"


class PlotKind(StrEnum):
    """Available plot types for visualization."""

    CORRELATION = "correlation"
    """A correlation heatmap of the original and avatar data."""

    CORRELATION_DIFFERENCE = "correlation_difference"
    """A heatmap of the difference between the original and avatar data."""

    CONTRIBUTION = "contribution"
    """A bar chart showing the contribution of each feature in the model."""

    PROJECTION_2D = "2d_projection"
    """A 2D projection of the original and avatar data."""

    PROJECTION_3D = "3d_projection"
    """A 3D projection of the original and avatar data."""

    DISTRIBUTION = "distribution"
    """Distributions plot of the original and avatar data, there is a plot for each column."""

    AGGREGATE_STATS = "aggregate_stats"
    """A table containing the mean and std of the original and avatar data
    (of the 10 first columns)."""

    RAW_SERIES = "raw_series"
    """A line plot of the original and avatar time series over time."""

    NORMALIZED_SERIES = "normalized_series"
    """A line plot of the normalized original and avatar time series over time."""


RESULTS_TO_STORE = [
    Results.SHUFFLED,
    Results.UNSHUFFLED,
    Results.PRIVACY_METRICS,
    Results.SIGNAL_METRICS,
    Results.PROJECTIONS_ORIGINAL,
    Results.PROJECTIONS_AVATARS,
    Results.METADATA,
    Results.FIGURES,
]

TypeResults = dict | pd.DataFrame | str | list[dict] | None | HTML

MATCHERS: dict[re.Pattern[str], ColumnType] = {
    re.compile(r"float"): ColumnType.NUMERIC,
    re.compile(r"int"): ColumnType.INT,
    re.compile(r"bool"): ColumnType.BOOL,
    re.compile(r"datetime"): ColumnType.DATETIME,
    re.compile(r"datetime64\[ns, UTC\]"): ColumnType.DATETIME_TZ,
    # FIXME: implement bool ColumnType
}

DEFAULT_TYPE = ColumnType.CATEGORY

mapping_result_to_file_name = {
    Results.ADVICE: "advice.json",
    Results.SHUFFLED: "shuffled",
    Results.UNSHUFFLED: "unshuffled",
    Results.PRIVACY_METRICS: "privacy.json",
    Results.SIGNAL_METRICS: "signal.json",
    Results.PROJECTIONS_ORIGINAL: "projections.original",
    Results.PROJECTIONS_AVATARS: "projections.avatars",
    Results.METADATA: "run_metadata.json",
    Results.REPORT: "report.md",
}
