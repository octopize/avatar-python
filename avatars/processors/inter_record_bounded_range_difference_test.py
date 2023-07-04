import numpy as np
import pandas as pd
import pandas.testing as pd_testing
import pytest
from pandas.testing import assert_frame_equal

from avatars.processors import InterRecordBoundedRangeDifferenceProcessor


@pytest.fixture
def df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "a_s": [30, 100, 80, 70, 40, 70],
            "a_e": [10, 80, 70, 60, 30, 5],
            "b": [4, 3, 0, 0, 2, 4],
            "id": [1, 1, 1, 2, 2, 2],
        }
    )
    return df


def test_process_and_inverse_returns_same_data(df: pd.DataFrame) -> None:
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
        sort_by_variable=None,
        should_round_output=False,
    )

    # Pre-process
    preprocessed_df = processor.preprocess(df)

    # Post-process transformed df
    postprocessed_df = processor.postprocess(df, preprocessed_df)

    pd_testing.assert_frame_equal(postprocessed_df, df, check_dtype=False)


def test_bounds_are_respected(df: pd.DataFrame) -> None:
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
        sort_by_variable=None,
        should_round_output=False,
    )

    # Pre-process
    preprocessed_df = processor.preprocess(df)

    # Post-process shuffled transformed df (this produces values out of bound with other processor)
    shuffled_preprocessed_df = preprocessed_df.sample(frac=1).reset_index(drop=True)
    postprocessed_df = processor.postprocess(df, shuffled_preprocessed_df)

    assert (
        sum(postprocessed_df["a_s"] < 5) == 0
    )  # we should not have any value lower than 5
    assert (
        sum(postprocessed_df["a_e"] < 5) == 0
    )  # we should not have any value lower than 5
    assert (
        sum(postprocessed_df["a_s"] > 100) == 0
    )  # we should not have any value greater than 100
    assert (
        sum(postprocessed_df["a_e"] > 100) == 0
    )  # we should not have any value greater than 100


def test_round_output_produces_integers(df: pd.DataFrame) -> None:
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
        sort_by_variable=None,
        should_round_output=True,
    )

    # Pre-process
    preprocessed_df = processor.preprocess(df)

    # Post-process shuffled transformed df (this produces values out of bound with other processor)
    postprocessed_df = processor.postprocess(df, preprocessed_df)

    assert postprocessed_df["a_s"].dtype in [np.int8, np.int16, np.int32, np.int64]
    assert postprocessed_df["a_e"].dtype in [np.int8, np.int16, np.int32, np.int64]


def test_sort_by_at_preprocess(df: pd.DataFrame) -> None:
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
        sort_by_variable="b",
        should_round_output=False,
    )

    # Pre-process
    preprocessed_df = processor.preprocess(df)

    expected = pd.DataFrame(
        {
            "b": [4, 3, 0, 0, 2, 4],
            "id": [1, 1, 1, 2, 2, 2],
            "a_range": [-0.8, -0.211, -0.133, -0.154, -0.286, -1.0],
            "a_s_first_val": [80, 80, 80, 70, 70, 70],
            "a_diff_to_bound": [-0.666, 1.0, 0.0, 0.0, -0.364, 0.571],
        }
    )

    assert_frame_equal(preprocessed_df, expected, rtol=0.01)


def test_preprocess_raises_error_when_wrong_variable_name(df: pd.DataFrame) -> None:
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="wrong_id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
    )

    with pytest.raises(
        ValueError,
        match="Expected valid variable names for",
    ):
        processor.preprocess(df)


def test_preprocess_raises_error_when_missing_values(df: pd.DataFrame) -> None:
    df.loc[1, "a_s"] = np.nan
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
    )

    with pytest.raises(
        ValueError,
        match="Expected no missing values for",
    ):
        processor.preprocess(df)


def test_extra_columns_are_kept_at_postprocess(df: pd.DataFrame) -> None:
    processor = InterRecordBoundedRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="a_s",
        target_end_variable="a_e",
        new_first_variable_name="a_s_first_val",
        new_difference_variable_name="a_diff_to_bound",
        new_range_variable="a_range",
        sort_by_variable=None,
        should_round_output=False,
    )

    # Pre-process
    preprocessed_df = processor.preprocess(df)

    # Add an extra variable (this would typically happen when preprocessing many variables)
    preprocessed_df["extra_variable_1"] = preprocessed_df["a_range"]
    df["extra_variable_2"] = df["a_s"]

    postprocessed_df = processor.postprocess(df, preprocessed_df)

    # Post-process df should have the additional variables from dest but not the additional
    # variables from source
    should_have_columns = df.columns.to_list() + ["extra_variable_1"]
    should_have_columns.remove("extra_variable_2")

    assert postprocessed_df.columns.tolist() == should_have_columns
