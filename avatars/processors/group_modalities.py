from typing import Dict, Optional

import pandas as pd

from avatars.lib.split_columns_types import split_columns_types


class GroupModalitiesProcessor:
    def __init__(
        self,
        *,
        variable_thresholds: Optional[Dict[str, int]] = None,
        min_unique: Optional[int] = None,
        global_threshold: Optional[int] = None,
        new_category: str = "other",
    ):
        """Processor to group modalities in order to reduce the dataframe dimension.

        Use the parameter `variables` if you want to apply a custom threshold to each variable.
        Use the parameter `min_unique` and `threshold` if you want to apply a generic threshold.

        Arguments
        ---------
            variable_thresholds: dictionary of variables and thresholds to apply,
            see global_threshold below.
            min_unique: number of unique modalities by variable needed to be transformed.
            global_threshold: limit of the number of individuals in each category
            to rename it.
            new_category: new modality name (default="other").
        """
        if (not min_unique and global_threshold) or (
            not global_threshold and min_unique
        ):
            raise ValueError(
                f"Expected both of (global_threshold, min_unique), got"
                f"{(global_threshold, min_unique)} instead."
            )

        if (not variable_thresholds and not global_threshold) or (
            variable_thresholds and global_threshold
        ):
            raise ValueError(
                f"Expected variable_thresholds or (threshold, min_unique),"
                f"got variable_thresholds {variable_thresholds} and "
                f"(threshold, min_unique) {(global_threshold, min_unique)} instead."
            )

        self.variable_thresholds = variable_thresholds
        self.min_unique = min_unique
        self.global_threshold = global_threshold
        self.new_category = new_category

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.variable_thresholds:
            variables = self.variable_thresholds.keys()
            if not all(elem in df.columns for elem in variables):
                unknown_variables = [
                    elem for elem in variables if elem not in df.columns
                ]
                raise ValueError(
                    "Expected valid variables in variable_thresholds",
                    f"got {unknown_variables} instead.",
                )

        df = df.copy()

        if not self.variable_thresholds:
            # select columns to transform
            _, category_index = split_columns_types(df)
            categories = df.columns[category_index]
            # Select columns to reduce
            count_category = df[categories].nunique()
            columns_to_reduce = count_category[
                count_category >= self.min_unique
            ].index.tolist()
            if self.global_threshold:
                self.variable_thresholds = {
                    x: self.global_threshold for x in columns_to_reduce
                }

        # Apply the modality transformation
        if self.variable_thresholds:  # TODO: fix me for mypy
            count = {
                x: df[x].value_counts().to_dict()
                for x in self.variable_thresholds.keys()
            }
            correspondence = {
                key: {
                    k: self.new_category
                    for k, v in value.items()
                    if v <= self.variable_thresholds[key]
                }
                for key, value in count.items()
            }
        df = df.replace(correspondence)

        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        return dest
