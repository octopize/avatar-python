from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from avatars.lib.split_columns_types import split_columns_types


@pytest.fixture
def many_dtypes_df() -> pd.DataFrame:
    df = pd.DataFrame()
    df["ints"] = [-2, 0, 2, 3, 4, 5, 6]
    df["floats"] = [-2.1, 0.0, 2.1, 3.1, 4.1, 5.1, 6.1]
    df["strings"] = ["Mr", "John", "Doe", "Mrs.", "Mary", "Higgins", "Clark"]
    df["datetimes"] = pd.to_datetime([datetime(2022, 1, 1).replace(tzinfo=None)] * 7)
    return df


def test_split_column_types(many_dtypes_df: pd.DataFrame) -> None:
    test_categorical = [2, 3]
    test_continuous = [0, 1]

    continuous, categorical = split_columns_types(many_dtypes_df)

    assert categorical == test_categorical
    assert continuous == test_continuous


def test_split_column_types_no_categorical(many_dtypes_df: pd.DataFrame) -> None:
    test_continuous, test_categorical = split_columns_types(
        many_dtypes_df[["ints", "floats"]]
    )

    assert len(test_categorical) == 0
    assert test_continuous == [0, 1]


def test_split_column_types_no_continuous(many_dtypes_df: pd.DataFrame) -> None:
    test_continuous, test_categorical = split_columns_types(
        many_dtypes_df[["strings", "datetimes"]]
    )

    assert test_categorical == [0, 1]
    assert len(test_continuous) == 0


@pytest.mark.parametrize("dtype_int", [np.int8, np.int16, np.int32, np.int64])
def test_split_column_types_different_int(
    many_dtypes_df: pd.DataFrame, dtype_int: np.int_
) -> None:
    test_categorical = [2, 3]
    test_continuous = [0, 1]

    df = many_dtypes_df
    df["ints"] = df["ints"].astype(dtype_int)
    continuous, categorical = split_columns_types(df)

    assert categorical == test_categorical
    assert continuous == test_continuous


@pytest.mark.parametrize("dtype_float", [np.float64, np.float32, np.float16])
def test_split_column_types_different_float(
    many_dtypes_df: pd.DataFrame, dtype_float: np.float_
) -> None:
    test_categorical = [2, 3]
    test_continuous = [0, 1]

    df = many_dtypes_df
    df["floats"] = df["floats"].astype(dtype_float)
    continuous, categorical = split_columns_types(df)

    assert categorical == test_categorical
    assert continuous == test_continuous
