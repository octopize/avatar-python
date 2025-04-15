import numpy as np
import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors import ProportionProcessor

ORIGINAL_DF = pd.DataFrame(
    {
        "variable_1": [100, 150, 120, 100],
        "variable_2": [10, 30, 30, np.nan],  # to test v2+v3+v4 = v1
        "variable_3": [30, 60, 30, np.nan],
        "variable_4": [60, 60, 60, np.nan],
        "variable_5": [90, 90, 90, np.nan],
    }
)
TRANSFORMED_DF = pd.DataFrame(
    {
        "variable_1": [100, 150, 120, 100],
        "variable_2": [0.1, 0.2, 0.25, np.nan],  # to test v2+v3+v4 = v1
        "variable_3": [0.3, 0.4, 0.25, np.nan],
        "variable_4": [0.6, 0.4, 0.5, np.nan],
        "variable_5": [0.9, 0.6, 0.75, np.nan],
    }
)


def test_preprocess_proportional_variables() -> None:
    # Check that three variables can be transformed into proportion of a fourth one.
    processor = ProportionProcessor(
        variable_names=["variable_2", "variable_3", "variable_4"],
        reference="variable_1",
        sum_to_one=True,
    )
    df = processor.preprocess(df=ORIGINAL_DF)
    pd_testing.assert_frame_equal(
        TRANSFORMED_DF[["variable_1", "variable_2", "variable_3", "variable_4"]],
        df[["variable_1", "variable_2", "variable_3", "variable_4"]],
    )


def test_postprocess_proportional_variables() -> None:
    # Check that three variables expressed as proportion can be re-expressed in their
    # original form.
    processor = ProportionProcessor(
        variable_names=["variable_2", "variable_3", "variable_4"],
        reference="variable_1",
        sum_to_one=True,
    )
    df = processor.postprocess(source=None, dest=TRANSFORMED_DF)
    pd_testing.assert_frame_equal(
        ORIGINAL_DF[["variable_1", "variable_2", "variable_3", "variable_4"]],
        df[["variable_1", "variable_2", "variable_3", "variable_4"]],
        check_dtype=False,
    )


def test_preprocess_proportional_single_variable() -> None:
    # Check that 1 variable can be transformed into proportion of another.
    processor = ProportionProcessor(
        variable_names=["variable_5"], reference="variable_1", sum_to_one=False
    )
    df = processor.preprocess(df=ORIGINAL_DF)
    pd_testing.assert_frame_equal(
        TRANSFORMED_DF[["variable_1", "variable_5"]],
        df[["variable_1", "variable_5"]],
    )


def test_postprocess_proportional_single_variable() -> None:
    # Check that 1 variable can be transformed into proportion of another.
    processor = ProportionProcessor(
        variable_names=["variable_5"], reference="variable_1", sum_to_one=False
    )
    df = processor.postprocess(source=None, dest=TRANSFORMED_DF)
    pd_testing.assert_frame_equal(
        ORIGINAL_DF[["variable_1", "variable_5"]],
        df[["variable_1", "variable_5"]],
        check_dtype=False,
    )


def test_preprocess_wrong_reference() -> None:
    processor = ProportionProcessor(
        variable_names=["variable_2"],
        reference="wrong_variable",
        sum_to_one=True,
    )
    with pytest.raises(
        ValueError,
        match="('variable_name', "
        "'variable wrong_variable cannot be found in the dataframe variables')",
    ):
        processor.preprocess(ORIGINAL_DF)


def test_postprocess_wrong_reference() -> None:
    processor = ProportionProcessor(
        variable_names=["variable_2"],
        reference="wrong_variable",
        sum_to_one=True,
    )
    with pytest.raises(
        ValueError,
        match="('variable_name', "
        "'variable wrong_variable cannot be found in the dataframe variables')",
    ):
        processor.postprocess(ORIGINAL_DF, ORIGINAL_DF)


def test_preprocess_reference_variable_zero() -> None:
    # Verify result contains proportions when reference is zero.
    df = pd.DataFrame(
        {
            "variable_1": [100, 0],
            "variable_2": [10, 10],
            "variable_3": [90, 30],
        }
    )
    processor = ProportionProcessor(
        variable_names=["variable_2", "variable_3"],
        reference="variable_1",
        sum_to_one=True,
    )
    preprocessed = processor.preprocess(df=df)
    expected = pd.DataFrame(
        {
            "variable_1": [100, 0],
            "variable_2": [0.1, 0.25],
            "variable_3": [0.9, 0.75],
        }
    )
    pd_testing.assert_frame_equal(preprocessed, expected)


def test_preprocess_target_variables_sum_zero() -> None:
    # Verify target variables that equal zero still equal zero after transformation
    df = pd.DataFrame(
        {
            "variable_1": [100, 100],
            "variable_2": [10, 0],
            "variable_3": [90, 0],
        }
    )
    processor = ProportionProcessor(
        variable_names=["variable_2", "variable_3"],
        reference="variable_1",
        sum_to_one=True,
    )
    preprocessed = processor.preprocess(df=df)
    expected = pd.DataFrame(
        {
            "variable_1": [100, 100],
            "variable_2": [0.1, 0],
            "variable_3": [0.9, 0],
        }
    )
    pd_testing.assert_frame_equal(preprocessed, expected)


def test_postprocess_saferounding() -> None:
    "Verify that the postprocessed variables sum up to reference variable."
    df = pd.DataFrame(
        {
            "variable_1": [101, 101],
            "variable_2": [34, 20],
            "variable_3": [66, 80],
        }
    )
    preprocessed = pd.DataFrame(
        {
            "variable_1": [101, 101],
            "variable_2": [0.34, 0.20],
            "variable_3": [0.66, 0.80],
        }
    )
    processor = ProportionProcessor(
        variable_names=["variable_2", "variable_3"],
        reference="variable_1",
        sum_to_one=True,
        decimal_count=0,
    )
    postprocessed = processor.postprocess(df, preprocessed)
    sum_check = postprocessed["variable_2"] + postprocessed["variable_3"]
    pd_testing.assert_series_equal(
        sum_check, postprocessed["variable_1"], check_names=False, check_dtype=False
    )


def test_decimals() -> None:
    "Verify that the postprocessed variables have the specified number of decimals."
    df = pd.DataFrame(
        {
            "variable_1": [101, 101],
            "variable_2": [34, 20],
            "variable_3": [66, 80],
        }
    )
    preprocessed = pd.DataFrame(
        {
            "variable_1": [101, 101],
            "variable_2": [0.34, 0.20],
            "variable_3": [0.66, 0.80],
        }
    )
    processor = ProportionProcessor(
        variable_names=["variable_2", "variable_3"],
        reference="variable_1",
        sum_to_one=True,
        decimal_count=2,
    )
    postprocessed = processor.postprocess(df, preprocessed)
    expected = pd.DataFrame(
        {
            "variable_1": [101, 101],
            "variable_2": [34.34, 20.20],
            "variable_3": [66.66, 80.80],
        }
    )
    pd_testing.assert_frame_equal(postprocessed, expected)
