from typing import List, Optional

import pandas as pd
import pandas.testing as pd_testing
import pytest

from avatars.processors import ExpectedMeanProcessor


@pytest.fixture
def original_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "variable_1": ["a", "a", "b", "b", "b"],
            "variable_2": [1, 3, 3, 4, 6],
            "variable_3": [3, 3, 1, 2, 3],
            "variable_4": [10, 9, 30, 40, 50],
        }
    )


@pytest.fixture
def raw_avatars_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "variable_1": ["a", "a", "b", "b", "b"],
            "variable_2": [1, 3, 3, 4, 6],
            "variable_3": [5, 3, 2, 2, 6],
            "variable_4": [8, 11, 20, 42, 55],
        }
    )


def test_preprocess_with_groupby(original_df: pd.DataFrame) -> None:
    # Verify that the calculated properties of the target variables are correct.
    # NB: pandas uses Bessel's correction to calculate std, while numpy does not. This brings
    # different std results on very small datasets. The expected values in the test is based on
    # the use of Bessel's correction.
    processor = ExpectedMeanProcessor(
        target_variables=["variable_3", "variable_4"],
        groupby_variables=["variable_1"],
        same_std=False,
    )
    processor.preprocess(df=original_df)
    expected = pd.DataFrame(
        {
            "variable_1": ["a", "b"],
            "variable_3mean": [3.0, 2.0],
            "variable_3std": [0.0, 1.0],
            "variable_4mean": [9.5, 40.0],
            "variable_4std": [0.707107, 10.0],
        }
    )

    pd_testing.assert_frame_equal(processor.properties_df, expected)


def test_postrocess_with_groupby(
    original_df: pd.DataFrame, raw_avatars_df: pd.DataFrame
) -> None:
    # Verify that the postprocessed dataframe is correct when using only
    # the mean to post-process the data.
    processor = ExpectedMeanProcessor(
        target_variables=["variable_3", "variable_4"],
        groupby_variables=["variable_1"],
        same_std=False,
    )
    processor.preprocess(df=original_df)
    fixed_avatars_df = processor.postprocess(source=original_df, dest=raw_avatars_df)
    expected = pd.DataFrame(
        {
            "variable_1": ["a", "a", "b", "b", "b"],
            "variable_2": [1, 3, 3, 4, 6],
            "variable_3": [4, 2, 0.66667, 0.66667, 4.66667],
            "variable_4": [8, 11, 21, 43, 56],
        }
    )

    pd_testing.assert_frame_equal(fixed_avatars_df, expected, check_dtype=False)


@pytest.mark.parametrize(
    "groupby_variables, expected",
    [
        (
            ["variable_1"],
            pd.DataFrame(
                {
                    "variable_1": ["a", "a", "b", "b", "b"],
                    "variable_2": [1, 3, 3, 4, 6],
                    "variable_3": [3, 3, 1.42265, 1.42265, 3.154701],
                    "variable_4": [9, 10, 29.260565, 41.6957, 49.043735],
                }
            ),
        ),
        (
            None,
            pd.DataFrame(
                {
                    "variable_1": ["a", "a", "b", "b", "b"],
                    "variable_2": [1, 3, 3, 4, 6],
                    "variable_3": [3.09, 2.10, 1.61, 1.61, 3.58],
                    "variable_4": [10.78, 13.44, 21.42, 40.92, 52.45],
                }
            ),
        ),
    ],
)
def test_postprocess_same_std(
    original_df: pd.DataFrame,
    raw_avatars_df: pd.DataFrame,
    groupby_variables: Optional[List[str]],
    expected: pd.DataFrame,
) -> None:
    # Verify that the postprocessed dataframe is correct when none of the
    # variables to transform has a std equal to zero.
    processor = ExpectedMeanProcessor(
        target_variables=["variable_3", "variable_4"],
        groupby_variables=groupby_variables,
        same_std=True,
    )
    processor.preprocess(df=original_df)
    fixed_avatars_df = processor.postprocess(source=original_df, dest=raw_avatars_df)

    pd_testing.assert_frame_equal(fixed_avatars_df, expected, atol=0.01)


@pytest.mark.filterwarnings("ignore:.*std of 0*")
def test_postrocess_same_std_with_zero_std() -> None:
    # Verify that the postprocessed dataframe is correct when one of the
    # variables to transform has a std equal to zero.
    original_df = pd.DataFrame(
        {
            "variable_1": ["a", "a", "b", "b", "b"],
            "variable_2": [1, 3, 3, 4, 6],
            "variable_3": [3, 4, 1, 2, 3],
            "variable_4": [10, 9, 30, 40, 50],
        }
    )
    processor = ExpectedMeanProcessor(
        target_variables=["variable_3", "variable_4"],
        groupby_variables=["variable_1"],
        same_std=True,
    )
    processor.preprocess(df=original_df)
    raw_avatars_df = pd.DataFrame(
        {
            "variable_1": ["a", "a", "b", "b", "b"],
            "variable_2": [1, 3, 3, 4, 6],
            "variable_3": [5, 3, 2, 2, 6],
            "variable_4": [8, 8, 20, 42, 55],
        }
    )
    fixed_avatars_df = processor.postprocess(source=original_df, dest=raw_avatars_df)
    expected = pd.DataFrame(
        {
            "variable_1": ["a", "a", "b", "b", "b"],
            "variable_2": [1, 3, 3, 4, 6],
            "variable_3": [4, 3, 1.42265, 1.42265, 3.154701],
            "variable_4": [9.5, 9.5, 21, 43, 56],
        }
    )

    pd_testing.assert_frame_equal(fixed_avatars_df, expected)


def test_preprocess_no_groupby(original_df: pd.DataFrame) -> None:
    # Verify that the calculated properties of the target variables are correct when using no
    # groupby.
    # NB: pandas uses Bessel's correction to calculate std, while numpy does not. This brings
    # different std results on very small datasets. The expected values in the test is based on
    # the use of Bessel's correction.
    processor = ExpectedMeanProcessor(
        target_variables=["variable_3", "variable_4"],
        groupby_variables=None,
        same_std=True,
    )
    processor.preprocess(df=original_df)
    expected = pd.DataFrame(
        {
            processor.nogroup_name: [processor.nogroup_value],
            "variable_3mean": [2.4],
            "variable_3std": [0.89],
            "variable_4mean": [27.8],
            "variable_4std": [18.14],
        }
    )

    pd_testing.assert_frame_equal(processor.properties_df, expected, atol=0.01)
