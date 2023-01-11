import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors import RelativeRangeProcessor

ORIGINAL_DF = pd.DataFrame(
    {
        "variable_1": [130, 230, 200],
        "variable_1_lb": [110, 180, 130],
        "variable_1_ub": [210, 340, 280],
    }
)
TRANSFORMED_DF = pd.DataFrame(
    {"variable_1_lb": [110, 180, 130], "variable_1_ub": [210, 340, 280]}
)


def test_preprocess() -> None:
    # Check that dataframe stays unchanged during preprocessing step
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("variable_1_lb", "variable_1_ub"),
        drop_references=True,
    )
    df = processor.preprocess(df=ORIGINAL_DF)

    pd_testing.assert_frame_equal(
        TRANSFORMED_DF,
        df,
    )


def test_postprocess() -> None:
    # Check that the transformed variable is within the desired range
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("variable_1_lb", "variable_1_ub"),
        drop_references=True,
    )
    _ = processor.preprocess(df=ORIGINAL_DF)
    df = processor.postprocess(source=None, dest=TRANSFORMED_DF)

    assert all(
        (df["variable_1"] > ORIGINAL_DF["variable_1_lb"])
        & (df["variable_1"] < ORIGINAL_DF["variable_1_ub"])
    )


def test_drop_references_true() -> None:
    # Check that only the target column is in the postprocessed dataframe
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("variable_1_lb", "variable_1_ub"),
        drop_references=True,
    )
    _ = processor.preprocess(df=ORIGINAL_DF)
    df = processor.postprocess(source=None, dest=TRANSFORMED_DF)

    assert list(df.columns) == ["variable_1"]


def test_drop_references_false() -> None:
    # Check that all original columns are in the postprocessed dataframe
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("variable_1_lb", "variable_1_ub"),
        drop_references=False,
    )
    _ = processor.preprocess(df=ORIGINAL_DF)
    df = processor.postprocess(source=None, dest=TRANSFORMED_DF)

    assert all(
        [col in df.columns for col in ["variable_1", "variable_1_lb", "variable_1_ub"]]
    )


def test_drop_target_false() -> None:
    # Check that all columns are in the preprocessed dataframe
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("variable_1_lb", "variable_1_ub"),
        drop_target=False,
    )
    df = processor.preprocess(df=ORIGINAL_DF)

    assert all(
        [col in df.columns for col in ["variable_1", "variable_1_lb", "variable_1_ub"]]
    )


def test_postprocess_with_out_of_range_values() -> None:
    # Check that the transformed variable is fixed within the desired range where
    # out of bound and that other values are kept
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("variable_1_lb", "variable_1_ub"),
        drop_references=True,
    )
    _ = processor.preprocess(df=ORIGINAL_DF)
    input_df = pd.DataFrame(
        {
            "variable_1": [220, 230, 200],
            "variable_1_lb": [110, 180, 130],
            "variable_1_ub": [210, 340, 280],
        }
    )
    df = processor.postprocess(source=None, dest=input_df)

    assert all(
        (df["variable_1"] > ORIGINAL_DF["variable_1_lb"])
        & (df["variable_1"] < ORIGINAL_DF["variable_1_ub"])
    )
    assert all([df.iloc[ind, 0] == input_df.iloc[ind, 0] for ind in [1, 2]])


def test_preprocess_wrong_bounds() -> None:
    processor = RelativeRangeProcessor(
        target="variable_1",
        bounds=("this_is_a_very_wrong_variable", "variable_1_ub"),
    )
    with pytest.raises(
        ValueError, match="Expected all bounds variables in dataset columns, got *"
    ):
        processor.preprocess(df=ORIGINAL_DF)
