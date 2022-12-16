from typing import Dict, Optional

import numpy as np
import pandas as pd
from toolz.dicttoolz import valfilter

from avatars.lib.split_columns_types import NUMERIC_DTYPES


class PerturbationProcessor:
    def __init__(
        self,
        perturbation_level: Optional[Dict[str, float]] = None,
        *,
        seed: Optional[int] = None,
    ):
        self.perturbation_level = perturbation_level
        self.generator = np.random.default_rng(seed)
        if self.perturbation_level:
            self.perturbated_items = valfilter(
                lambda level: level != 1.0, self.perturbation_level
            )

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:

        if not self.perturbation_level:
            return dest

        missing_keys = set(self.perturbation_level.keys()).difference(source.columns)
        if missing_keys:
            raise ValueError(
                "perturbation_level",
                f"variables {missing_keys} cannot be found in the dataframe",
            )

        for column, values in self.perturbated_items.items():
            if dest[column].dtypes in NUMERIC_DTYPES:
                # for continuous data we apply a percentage of the difference
                dest[column] = source[column] + (
                    (dest[column] - source[column]) * values
                )
            else:
                # for categorical data we apply a random choice weighted by perturbation level
                indices = self.generator.choice(
                    [0, 1], source.shape[0], p=[1 - values, values], replace=True
                )

                # Choose either to take the sample from source or from dest
                choices = np.choose(
                    indices,
                    [
                        source[column].to_numpy().ravel(),
                        dest[column].to_numpy().ravel(),
                    ],
                )
                dest[column] = choices
        return dest
