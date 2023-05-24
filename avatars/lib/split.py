import math
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


def get_split_for_batch(
    df: pd.DataFrame,
    row_limit: int,
    seed: Optional[int] = None,
) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:
    """Create batches from a dataframe with the format (training, splits).


    Arguments
    ---------
        df:
            dataframe to split into batch
        row_limit:
            maximum number of row by batch, this parameter determine the number of batch that will be created

    Keyword Arguments
    -----------------
        seed:
            seed of the random split for the batch

    Returns
    -------
        training:
            the training batch that will be used to fit the anonymization
        training:
            splits: all other batches

    Examples
    --------    
    >>> df = pd.DataFrame(
    ... data={
    ...     "a": [1, 3, 5, 1, 3, 5, 1, 3, 5, 1, 3, 5],
    ...     "b": ["a", "b", "a", "a", "b", "a", "a", "b", "a", "a", "b", "a"],
    ...     }
    ... )
    >>> training, splits = get_split_for_batch(df, row_limit=6, seed=42)
    >>> training
       a  b
    0  1  a
    1  3  b
    2  3  b
    3  1  a
    4  3  b
    5  5  a
    >>> splits
    [   a  b
    0  1  a
    1  3  b
    2  5  a
    3  1  a
    4  5  a
    5  5  a]

    """
    number_of_split = math.ceil(len(df) / row_limit)
    categorical_columns = df.select_dtypes(include=["object", "category"]).columns

    index = get_index_without_duplicated_modalities(df[categorical_columns])
    first_occurrence = df.loc[index, :]
    if len(first_occurrence) > row_limit * 0.5:
        raise ValueError(
            "You have too much variability in your categorical data."
            "You can: change your row_limit, reduce your categorical variability, or built "
            "yur own batch pipeline."
        )

    df_without_first = df.drop(index=first_occurrence.index).reset_index(drop=True)
    first_occurrence.reset_index(drop=True, inplace=True)

    shuffled = df_without_first.sample(frac=1, random_state=seed)

    all_df = pd.concat([first_occurrence, shuffled]).reset_index(drop=True)
    splits = np.array_split(all_df, number_of_split)
    splits = [pd.DataFrame(split).reset_index(drop=True) for split in splits]
    training = splits.pop(0)

    return training, splits


def get_index_without_duplicated_modalities(df: pd.DataFrame) -> List[int]:
    values: Dict[str, Dict[str, bool]] = {col: {} for col in df.columns}
    df_array = np.array(df)
    index_to_keep = []
    for i in range(df_array.shape[0]):
        should_keep_row = False
        for j in range(df_array.shape[1]):
            try:
                values[df.columns[j]][df_array[i, j]]
            except KeyError:
                values[df.columns[j]][df_array[i, j]] = True
                should_keep_row = True
        if should_keep_row:
            index_to_keep.append(i)
    return index_to_keep
