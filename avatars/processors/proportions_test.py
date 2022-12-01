import numpy as np
import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors.proportions import ProportionProcessor

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