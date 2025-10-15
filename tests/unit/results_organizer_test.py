import pandas as pd
import pytest
from IPython.display import HTML

from avatars.constants import PlotKind, Results
from avatars.models import JobKind
from avatars.results_organizer import ResultsOrganizer


def assert_equals(expected, result):
    if isinstance(expected, pd.DataFrame):
        assert isinstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result, expected)
    elif isinstance(expected, list):
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)
        assert result == expected
    elif isinstance(expected, HTML):
        assert isinstance(result, dict)
        assert result[PlotKind.CORRELATION][0] == expected
    elif isinstance(expected, dict):
        assert isinstance(result, dict)
        assert result == expected
    else:
        raise TypeError(f"Unsupported type: {type(result)}")


@pytest.mark.parametrize(
    "result_name, job_kind, result, metadata,expected_type",
    [
        (
            Results.SHUFFLED,
            JobKind.standard,
            pd.DataFrame({"col1": [1, 2], "col2": [3, 4]}),
            None,
            pd.DataFrame,
        ),
        (
            Results.UNSHUFFLED,
            JobKind.standard,
            pd.DataFrame({"col1": [5, 6], "col2": [7, 8]}),
            None,
            pd.DataFrame,
        ),
        (Results.PRIVACY_METRICS, JobKind.privacy_metrics, [{"hidden_rate": 0.1}], None, list),
        (Results.SIGNAL_METRICS, JobKind.signal_metrics, [{"hellinger_mean": 0.1}], None, list),
        (
            Results.FIGURES,
            JobKind.standard,
            HTML("<div>Figure</div>"),
            {"kind": PlotKind.CORRELATION},
            [HTML],
        ),
        (Results.METADATA, JobKind.standard, {"key": "value"}, {"kind": JobKind.standard}, dict),
        (
            Results.PROJECTIONS_ORIGINAL,
            JobKind.standard,
            pd.DataFrame({"col1": [1, 2], "col2": [3, 4]}),
            None,
            pd.DataFrame,
        ),
        (
            Results.PROJECTIONS_AVATARS,
            JobKind.standard,
            pd.DataFrame({"col1": [1, 2], "col2": [3, 4]}),
            None,
            pd.DataFrame,
        ),
    ],
    ids=[
        "shuffled",
        "unshuffled",
        "privacy_metrics",
        "signal_metrics",
        "figures",
        "metadata",
        "projections_original",
        "projections_avatars",
    ],
)
def test_set_then_get_results(result_name, job_kind, result, metadata, expected_type):
    organizer = ResultsOrganizer()

    organizer.set_results(result_name, result, "table", metadata)
    retrieved = organizer.get_results("table", result_name, job_kind)

    assert_equals(result, retrieved)


def test_set_then_get_results_advice():
    organizer = ResultsOrganizer()

    organizer.set_results(
        Results.ADVICE,
        [{"table_name": "table", "advice": {"parameters": {"k": 10}}}],
        "table",
    )
    retrieved = organizer.get_results("table", Results.ADVICE, JobKind.advice)

    assert_equals({"parameters": {"k": 10}}, retrieved)


def test_unescape_table_name():
    organizer = ResultsOrganizer()
    escaped_name = "table_dot_name_slash_test"
    unescaped_name = organizer.unescape_table_name(escaped_name)
    assert unescaped_name == "table.name/test"
