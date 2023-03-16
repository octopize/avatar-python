import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from avatars.processors import InterRecordRangeDifferenceProcessor


@pytest.fixture
def df_with_cumulated() -> pd.DataFrame:
    # Values in the test data is purposely not ordered by id nor value
    df = pd.DataFrame(
        {
            "id": [1, 2, 1, 1, 2, 2],
            "start": [7, 14, 6, 12, 10, 23],
            "end": [8, 18, 7, 15, 12, 24],
        }
    )
    return df


@pytest.fixture
def preprocessed_df_with_cumulated() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "id": [1, 2, 1, 1, 2, 2],
            "range_value": [1, 4, 1, 3, 2, 1],
            "first_value": [6, 10, 6, 6, 10, 10],
            "value_difference": [0, 2, 0, 4, 0, 5],
        }
    )
    return df


def test_preprocess(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    "Verify that the preprocess is correct."
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    processed_df = processor.preprocess(df_with_cumulated)
    print(processed_df)

    assert_frame_equal(processed_df, preprocessed_df_with_cumulated, check_dtype=False)


def test_postprocess(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    "Verify that the postprocess is correct."
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    postprocessed_df = processor.postprocess(
        df_with_cumulated, preprocessed_df_with_cumulated
    )
    print(postprocessed_df)
    assert_frame_equal(postprocessed_df, df_with_cumulated, check_dtype=False)


def test_preprocess_raises_error_when_missing_values(
    df_with_cumulated: pd.DataFrame,
) -> None:
    df_with_cumulated.loc[0, "end"] = np.nan
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected no missing values for"):
        processor.preprocess(df_with_cumulated)


def test_preprocess_raises_error_when_wrong_var(
    df_with_cumulated: pd.DataFrame,
) -> None:
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="wrong_start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected valid variable names for"):
        processor.preprocess(df_with_cumulated)


def test_postprocess_raises_error_when_wrong_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="start",
        new_first_variable_name="first_value",
        new_range_variable_name="wrong_range_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected valid variable names for"):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_wrong_sort_by_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="wrong_start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected a valid `sort_by_variable_name`, got"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_missing_values(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    preprocessed_df_with_cumulated.loc[3, "first_value"] = np.nan
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected no missing values for"):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_missing_sort_by_values(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    df_with_cumulated.loc[3, "start"] = np.nan
    processor = InterRecordRangeDifferenceProcessor(
        id_variable="id",
        target_start_variable="start",
        target_end_variable="end",
        sort_by_variable_name="start",
        new_first_variable_name="first_value",
        new_range_variable_name="range_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for `sort_by_variable_name`"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)
