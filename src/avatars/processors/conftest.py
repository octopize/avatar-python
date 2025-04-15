from datetime import datetime

import pandas as pd
import pytest


@pytest.fixture
def many_dtypes_df() -> pd.DataFrame:
    df = pd.DataFrame()
    df["ints"] = [-2, 0, 2, 3, 4, 5, 6]
    df["floats"] = [-2.1, 0.0, 2.1, 3.1, 4.1, 5.1, 6.1]
    df["strings"] = ["Mr", "John", "Doe", "Mrs.", "Mary", "Higgins", "Clark"]
    df["datetimes"] = pd.to_datetime([datetime(2022, 1, 1).replace(tzinfo=None)] * 7)
    return df


@pytest.fixture
def categorical_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "variable_1": ["red", "blue", "blue", "green"],
            "variable_2": ["red", "blue", "blue", "red"],
            "variable_3": ["green", "green", "green", "green"],
        }
    )
    return df


@pytest.fixture
def dates_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "date_1": ["2015-01-01 07:00:00", "2015-01-01 10:00:00"],
            "date_2": ["2018-01-01 11:00:00", "2020-01-01 11:00:00"],
        }
    )
    df["date_1"] = pd.to_datetime(df["date_1"], format="%Y-%m-%d %H:%M:%S")
    df["date_2"] = pd.to_datetime(df["date_2"], format="%Y-%m-%d %H:%M:%S")
    return df
