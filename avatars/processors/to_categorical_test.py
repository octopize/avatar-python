import numpy as np
import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors import ToCategoricalProcessor


@pytest.fixture
def original() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "variable_1": [1, 2, 3, np.nan],
            "variable_2": [1, 2, 2, np.nan],
        }
    )
    return df


def test_preprocess_to_categorical_keep_continuous(original: pd.DataFrame) -> None:
    """Check preprocess with keep continuous."""
    expected = original.copy()
    expected["variable_2__cont"] = expected["variable_2"]
    expected = expected.astype({"variable_2": "object"})

    processor = ToCategoricalProcessor(to_categorical_threshold=2, keep_continuous=True)
    df = processor.preprocess(df=original)

    pd_testing.assert_frame_equal(expected, df)


def test_preprocess_to_categorical(original: pd.DataFrame) -> None:
    """Check preprocess without keep continuous."""
    expected = original.copy()
    expected = expected.astype({"variable_2": "object"})

    processor = ToCategoricalProcessor(to_categorical_threshold=2)
    processed = processor.preprocess(df=original)

    pd_testing.assert_frame_equal(expected, processed)


def test_processor_to_categorical(original: pd.DataFrame) -> None:
    """Verify that pre- and post-process, with keep_continuous=False, gives original."""
    expected = original.copy()
    processor = ToCategoricalProcessor(
        to_categorical_threshold=2, keep_continuous=False
    )
    processed_df = processor.preprocess(df=original)
    df = processor.postprocess(source=original, dest=processed_df)

    pd_testing.assert_frame_equal(df, expected)


def test_processor_to_categorical_keep_continuous(original: pd.DataFrame) -> None:
    """Verify that pre- and post-process, with keep_continuous=True, gives original."""
    expected = original.copy()
    processor = ToCategoricalProcessor(to_categorical_threshold=2, keep_continuous=True)
    processed_df = processor.preprocess(df=original)
    df = processor.postprocess(source=original, dest=processed_df)
    pd_testing.assert_frame_equal(df, expected)


def test_postprocessed_with_category(original: pd.DataFrame) -> None:
    """Check post processor with a transformed variable changed the categorical variable.

    Transformed data frame could be obtained with another processor such as GroupModalities().
    """
    transformed = pd.DataFrame(
        {
            "variable_1": [1, 2, 3, np.nan],
            "variable_2": ["other", "other", "other", np.nan],
            "variable_2__cont": [1, 2, 2, np.nan],
        }
    )
    processor = ToCategoricalProcessor(
        to_categorical_threshold=2, keep_continuous=True, category="other"
    )
    _ = processor.preprocess(
        df=original
    )  # Needed to to add self.continuous_variables to the model
    df = processor.postprocess(source=original, dest=transformed)
    pd_testing.assert_series_equal(df["variable_2"], original["variable_2"])
