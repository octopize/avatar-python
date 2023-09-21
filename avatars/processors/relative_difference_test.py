import numpy as np
import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors import RelativeDifferenceProcessor

ORIGINAL_DF = pd.DataFrame(
    {
        "variable_1": [100, 150, 120, 100],
        "variable_5": [110, 180, 130, 100],
        "variable_6": [210, 340, 280, 220],
        "variable_7": [110, 180, 130, np.nan],
    }
)
TRANSFORMED_DF = pd.DataFrame(
    {
        "variable_1": [100, 150, 120, 100],
        "variable_5": [10, 30, 10, 0],
        "variable_6": [0, 10, 30, 20],
        "variable_7": [110, 180, 130, np.nan],
    }
)


def test_preprocess_one_variable() -> None:
    # Check that one variable is transformed into a relative difference to another one.
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["variable_1"],
    )
    df = processor.preprocess(df=ORIGINAL_DF)

    pd_testing.assert_frame_equal(
        TRANSFORMED_DF[["variable_1", "variable_5"]],
        df[["variable_1", "variable_5"]],
        check_dtype=False,
    )


def test_preprocess_many_variables() -> None:
    # Check that one variable is transformed into a relative difference to a group
    # of other variables.
    processor = RelativeDifferenceProcessor(
        target="variable_6",
        references=["variable_1", "variable_5"],
    )
    df = processor.preprocess(df=ORIGINAL_DF)

    pd_testing.assert_frame_equal(
        TRANSFORMED_DF[["variable_6"]],
        df[["variable_6"]],
        check_dtype=False,
    )


def test_postprocess_one_variable() -> None:
    # Check that one variable transformed into a relative difference to another one can
    # be re-expressed in its original form.
    processor = RelativeDifferenceProcessor(
        target="variable_5", references=["variable_1"]
    )
    df = processor.postprocess(source=None, dest=TRANSFORMED_DF)

    pd_testing.assert_frame_equal(
        ORIGINAL_DF[["variable_1", "variable_5"]],
        df[["variable_1", "variable_5"]],
    )


def test_postprocess_many_variables() -> None:
    # Check that one variable is transformed into a relative difference to a group of
    # other variables can be re-expressed in its original form.
    processor = RelativeDifferenceProcessor(
        target="variable_6", references=["variable_1", "variable_5"]
    )
    pre_df = processor.preprocess(df=ORIGINAL_DF)
    post_df = processor.postprocess(source=None, dest=pre_df)

    pd_testing.assert_frame_equal(
        ORIGINAL_DF[["variable_1", "variable_5", "variable_6"]],
        post_df[["variable_1", "variable_5", "variable_6"]],
        check_dtype=False,
    )


def test_preprocess_postprocess_many_variables() -> None:
    processor = RelativeDifferenceProcessor(
        target="variable_6", references=["variable_1", "variable_5"]
    )
    pre_df = processor.preprocess(df=ORIGINAL_DF)
    post_df = processor.postprocess(source=ORIGINAL_DF, dest=pre_df)

    pd_testing.assert_frame_equal(
        ORIGINAL_DF,
        post_df,
        check_dtype=False,
    )


def test_preprocess_raises_when_nan_in_references() -> None:
    processor = RelativeDifferenceProcessor(
        target="variable_1",
        references=["variable_7"],
    )
    with pytest.raises(ValueError, match="Expected no missing values for `references`"):
        processor.preprocess(df=ORIGINAL_DF)


def test_preprocess_with_rename_nodrop() -> None:
    """Verify that a new column is created and original target column kept."""
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["variable_1"],
        target_rename="variable_5_renamed",
    )
    df = processor.preprocess(df=ORIGINAL_DF)
    assert "variable_5" in df.columns and "variable_5_renamed" in df.columns


def test_preprocess_with_rename_drop() -> None:
    """Verify that a new column is created and original target column dropped."""
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["variable_1"],
        target_rename="variable_5_renamed",
        drop_original_target=True,
    )
    df = processor.preprocess(df=ORIGINAL_DF)
    assert "variable_5" not in df.columns and "variable_5_renamed" in df.columns


@pytest.mark.parametrize("drop_original_target", [True, False])
def test_postprocess_with_rename(drop_original_target: bool) -> None:
    """Verify that the transformed and renamed variable can be inverse transformed."""
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["variable_1"],
        target_rename="variable_5_renamed",
        drop_original_target=drop_original_target,
    )
    df = processor.preprocess(df=ORIGINAL_DF)
    df = processor.postprocess(source=None, dest=df)

    pd_testing.assert_frame_equal(
        ORIGINAL_DF[["variable_1", "variable_5"]],
        df[["variable_1", "variable_5"]],
        check_dtype=False,
    )


@pytest.mark.parametrize("scaling_unit", [2, 10])
def test_preprocess_with_scaling_unit(scaling_unit: int) -> None:
    """Verify that scaling_unit_parameter is working for preprocess."""
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["variable_1"],
        scaling_unit=scaling_unit,
    )
    df = processor.preprocess(df=ORIGINAL_DF)

    pd_testing.assert_frame_equal(
        TRANSFORMED_DF[["variable_5"]] / scaling_unit,
        df[["variable_5"]],
        check_dtype=False,
    )


@pytest.mark.parametrize("scaling_unit", [2, 10])
def test_postprocess_with_scaling_unit(scaling_unit: int) -> None:
    """Verify that scaling_unit_parameter is working for postprocess."""
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["variable_1"],
        scaling_unit=scaling_unit,
    )
    df = processor.preprocess(df=ORIGINAL_DF)
    df = processor.postprocess(source=None, dest=df)

    pd_testing.assert_frame_equal(df, ORIGINAL_DF, check_dtype=False)


def test_preprocess_wrong_parameters() -> None:
    with pytest.raises(
        ValueError,
        match="Expected drop_original_target to be False if a target_rename is None*",
    ):
        RelativeDifferenceProcessor(
            target="variable_5",
            references=["variable_1"],
            target_rename=None,
            drop_original_target=True,
        )


def test_preprocess_wrong_references_variables() -> None:
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["wrong_variable"],
        target_rename="None",
    )

    with pytest.raises(
        ValueError, match="Expected all reference variables in dataset columns, got *"
    ):
        processor.preprocess(df=ORIGINAL_DF)


def test_postprocess_wrong_references_variables() -> None:
    processor = RelativeDifferenceProcessor(
        target="variable_5",
        references=["wrong_variable"],
        target_rename="None",
    )

    with pytest.raises(
        ValueError, match="Expected all reference variables in dataset columns, got *"
    ):
        processor.postprocess(ORIGINAL_DF, ORIGINAL_DF)
