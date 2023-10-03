import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from avatars.processors import InterRecordBoundedCumulatedDifferenceProcessor


@pytest.fixture
def df_with_cumulated() -> pd.DataFrame:
    # Values in the test data is not ordered by id nor value
    df = pd.DataFrame(
        {
            "id": [1, 2, 1, 1, 2, 2],
            "value": [1025, 20042, 1000, 1130, 20000, 20040],
        }
    )
    return df


@pytest.fixture
def preprocessed_df_with_cumulated() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "id": [1, 2, 1, 1, 2, 2],
            "first_value": [1025, 20042, 1025, 1025, 20042, 20042],
            "difference_to_bound": [0, 0, -1, 0.006827, -0.002206, 0.952381],
        }
    )
    return df


def test_preprocess_raises_error_when_missing_ids(
    df_with_cumulated: pd.DataFrame,
) -> None:
    df_with_cumulated.loc[0, "id"] = np.nan
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(ValueError, match="Expected no missing values for id variable"):
        processor.preprocess(df_with_cumulated)


def test_preprocess_raises_error_when_missing_in_target(
    df_with_cumulated: pd.DataFrame,
) -> None:
    df_with_cumulated.loc[2, "value"] = np.nan
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for target variable"
    ):
        processor.preprocess(df_with_cumulated)


def test_postprocess_raises_error_when_missing_in_source_ids(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    df_with_cumulated.loc[0, "id"] = np.nan

    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for id variable in source"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_preprocess_raises_error_when_missing_in_source_target(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    df_with_cumulated.loc[2, "value"] = np.nan

    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for target variable in source"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_missing_in_dest_first_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    preprocessed_df_with_cumulated.loc[4, "first_value"] = np.nan

    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for `new_first_variable_name`"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_preprocess_raises_error_when_missing_in_dest_difference_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    preprocessed_df_with_cumulated.loc[2, "difference_to_bound"] = np.nan

    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(
        ValueError,
        match="Expected no missing values for `new_difference_variable_name`",
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_preprocess_raises_error_when_wrong_id_var(
    df_with_cumulated: pd.DataFrame,
) -> None:
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="wrong_id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(ValueError, match="Expected a valid `id_variable`"):
        processor.preprocess(df_with_cumulated)


def test_preprocess_raises_error_when_wrong_target_var(
    df_with_cumulated: pd.DataFrame,
) -> None:
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="wrong_value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(ValueError, match="Expected a valid `target_variable`"):
        processor.preprocess(df_with_cumulated)


def test_postprocess_raises_error_when_wrong_first_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="wrong_first_value",
        new_difference_variable_name="difference_to_bound",
    )

    with pytest.raises(ValueError, match="Expected a valid `new_first_variable_name`"):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_wrong_difference_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="wrong_difference_to_bound",
    )

    with pytest.raises(
        ValueError, match="Expected a valid `new_difference_variable_name`"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_bounds_are_respected(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordBoundedCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="difference_to_bound",
        should_round_output=True,
    )
    # Pre-process
    preprocessed_df = processor.preprocess(df_with_cumulated)
    assert_frame_equal(
        preprocessed_df, preprocessed_df_with_cumulated, check_dtype=False, atol=0.001
    )

    # Post-process transformed df
    postprocessed_df = processor.postprocess(df_with_cumulated, preprocessed_df)
    assert_frame_equal(
        postprocessed_df, df_with_cumulated, check_dtype=False
    )  # should be equal to original data

    # Post-process shuffled transformed df (i.e. what used to produce values out of bound)
    postprocessed_df = processor.postprocess(
        df_with_cumulated, preprocessed_df.sample(frac=1)
    )
    assert (
        sum(postprocessed_df["value"] < min(df_with_cumulated["value"])) == 0
    )  # we should not have any value lower than min(value)
    assert (
        sum(postprocessed_df["value"] > max(df_with_cumulated["value"])) == 0
    )  # we should not have any value greater than max(value)
