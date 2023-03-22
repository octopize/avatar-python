from typing import Any

import numpy as np
import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors import DatetimeProcessor


@pytest.fixture
def processor() -> Any:
    return DatetimeProcessor()


def test_preprocess_datetime(dates_df: pd.DataFrame, processor: Any) -> None:
    test_df = processor.preprocess(dates_df)
    expected = pd.DataFrame(
        {"date_1": [1.420096e09, 1.420106e09], "date_2": [1.514804e09, 1.577876e09]}
    )
    assert not pd.api.types.is_datetime64_dtype(test_df["date_1"])
    pd_testing.assert_frame_equal(test_df, expected)


def test_preprocess_postprocess_datetime(
    many_dtypes_df: pd.DataFrame, processor: Any
) -> None:
    """Verify that preprocessing and postprocessing datetime yields original dataframe."""
    df = many_dtypes_df
    expected = many_dtypes_df.copy()
    test_df = processor.preprocess(df)
    test_df = processor.postprocess(df, test_df)

    pd_testing.assert_frame_equal(test_df, expected)


def test_preprocess_and_postprocess_handle_nan(
    dates_df: pd.DataFrame, processor: Any
) -> None:
    dates_df.loc[0, "date_1"] = np.nan
    expected = dates_df.copy()
    test_df = processor.preprocess(dates_df)
    test_df = processor.postprocess(dates_df, test_df)

    pd_testing.assert_frame_equal(test_df, expected)
