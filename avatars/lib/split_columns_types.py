from typing import List, Tuple

import numpy as np
import pandas as pd

NUMERIC_DTYPES = [
    np.float64,
    np.float32,
    np.float16,
    np.int64,
    np.int32,
    np.int16,
    np.int8,
    np.uint8,
    np.uint16,
    np.uint32,
    np.uint64,
    np.complex64,
    np.complex128,
]


def split_columns_types(data_frame: pd.DataFrame) -> Tuple[List[int], List[int]]:
    """Split series of a pandas dataframe based on their type (continuous or categorical).

    Arguments
    ---------
        data_frame

    Returns
    -------
        array: two arrays of column indices,
            respectively for continuous and categorical variables
    """
    continuous = [
        idx
        for idx, name in enumerate(data_frame.columns)
        if data_frame[name].dtype in NUMERIC_DTYPES
    ]
    categorical = filter(lambda x: x not in continuous, range(0, data_frame.shape[1]))
    return continuous, list(categorical)
