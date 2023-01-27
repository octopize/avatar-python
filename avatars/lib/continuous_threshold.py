from typing import List

import pandas as pd

CATEGORICAL_DTYPES = ["object", "category", "boolean"]


def get_continuous_under_threshold(
    df: pd.DataFrame, *, threshold: int = 10
) -> List[str]:
    """Get continuous variable names with number of unique values under a threshold."""
    columns_to_check = df.select_dtypes(exclude=CATEGORICAL_DTYPES).columns
    return list(filter(lambda col: df[col].nunique() <= threshold, columns_to_check))
