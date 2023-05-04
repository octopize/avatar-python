import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from avatars.processors import InterRecordCumulatedDifferenceProcessor


@pytest.fixture
def df_with_cumulated() -> pd.DataFrame:
    # Values in the test data is purposely not ordered by id nor value
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
            "first_value": [1000, 20000, 1000, 1000, 20000, 20000],
            "value_difference": [25, 2, 0, 105, 0, 40],
        }
    )
    return df


def test_preprocess(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    "Verify that the preprocess is correct."
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    processed_df = processor.preprocess(df_with_cumulated)

    assert_frame_equal(processed_df, preprocessed_df_with_cumulated, check_dtype=False)


def test_postprocess_with_keep_order(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    "Verify that the postprocess is correct."
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
        keep_record_order=True,
    )

    postprocessed_df = processor.postprocess(
        df_with_cumulated, preprocessed_df_with_cumulated
    )
    assert_frame_equal(postprocessed_df, df_with_cumulated, check_dtype=False)


def test_postprocess_without_keep_order(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    "Verify that the postprocess is correct."
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
        keep_record_order=False,
    )

    # make indices of processed_df different than those of df_with_cumulated
    preprocessed_df_with_cumulated.index = range(
        10, 10 + len(preprocessed_df_with_cumulated), 1
    )

    # records should be decoded following row order
    expected = pd.DataFrame(
        {
            "id": [1, 2, 1, 1, 2, 2],
            "value": [1025, 20002, 1025, 1130, 20002, 20042],
        }
    )
    postprocessed_df = processor.postprocess(
        df_with_cumulated, preprocessed_df_with_cumulated
    ).reset_index(drop=True)

    assert_frame_equal(postprocessed_df, expected, check_dtype=False)


def test_preprocess_raises_error_when_missing_ids(
    df_with_cumulated: pd.DataFrame,
) -> None:
    df_with_cumulated.loc[0, "id"] = np.nan
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected no missing values for id variable"):
        processor.preprocess(df_with_cumulated)


def test_preprocess_raises_error_when_missing_target(
    df_with_cumulated: pd.DataFrame,
) -> None:
    df_with_cumulated.loc[2, "value"] = np.nan
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for target variable"
    ):
        processor.preprocess(df_with_cumulated)


def test_postprocess_raises_error_when_missing_source_ids(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    df_with_cumulated.loc[0, "id"] = np.nan

    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for id variable in source"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_preprocess_raises_error_when_missing_source_target(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    df_with_cumulated.loc[2, "value"] = np.nan

    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for target variable in source"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_missing_dest_first_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    preprocessed_df_with_cumulated.loc[4, "first_value"] = np.nan

    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected no missing values for `new_first_variable_name`"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_preprocess_raises_error_when_missing_dest_difference_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    preprocessed_df_with_cumulated.loc[2, "value_difference"] = np.nan

    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(
        ValueError,
        match="Expected no missing values for `new_difference_variable_name`",
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_preprocess_raises_error_when_wrong_id_var(
    df_with_cumulated: pd.DataFrame,
) -> None:
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="wrong_id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected a valid `id_variable`"):
        processor.preprocess(df_with_cumulated)


def test_preprocess_raises_error_when_wrong_target_var(
    df_with_cumulated: pd.DataFrame,
) -> None:
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="wrong_value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected a valid `target_variable`"):
        processor.preprocess(df_with_cumulated)


def test_postprocess_raises_error_when_wrong_first_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="wrong_first_value",
        new_difference_variable_name="value_difference",
    )

    with pytest.raises(ValueError, match="Expected a valid `new_first_variable_name`"):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_when_wrong_difference_var(
    df_with_cumulated: pd.DataFrame, preprocessed_df_with_cumulated: pd.DataFrame
) -> None:
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="wrong_value_difference",
    )

    with pytest.raises(
        ValueError, match="Expected a valid `new_difference_variable_name`"
    ):
        processor.postprocess(df_with_cumulated, preprocessed_df_with_cumulated)


def test_postprocess_raises_error_with_keep_order_and_different_indices(
    df_with_cumulated: pd.DataFrame,
) -> None:
    processor = InterRecordCumulatedDifferenceProcessor(
        id_variable="id",
        target_variable="value",
        new_first_variable_name="first_value",
        new_difference_variable_name="value_difference",
        keep_record_order=True,
    )

    processed_df = processor.preprocess(df_with_cumulated)
    # make indices of processed_df different than those of df_with_cumulated
    processed_df.index = range(10, 10 + len(processed_df), 1)

    with pytest.raises(
        ValueError,
        match="Expected `keep_record_order` to be `True` only if",
    ):
        processor.postprocess(df_with_cumulated, processed_df)
