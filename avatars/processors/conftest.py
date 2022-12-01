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
