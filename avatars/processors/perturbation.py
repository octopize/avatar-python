from typing import Dict, Optional

import numpy as np
import pandas as pd
from toolz.dicttoolz import valfilter

from avatars.lib.split_columns_types import NUMERIC_DTYPES


class PerturbationProcessor:
    """Processor to reduce the difference between originals and avatars.

    Specifies the perturbation level of specified variables, 0 means no perturbation.
    (default: ``np.ones(df.shape[1])``)

    Arguments
    ---------
        perturbation_level:
            variables and perturbation level

    Keyword Arguments
    -----------------
        seed:
            A seed to initialize the BitGenerator.

    Examples
    --------
    >>> import numpy as np
    >>> df = pd.DataFrame(np.zeros(3), columns=["column"], dtype="float")
    >>> df
       column
    0     0.0
    1     0.0
    2     0.0
    >>> processor = PerturbationProcessor(perturbation_level={"column": 0.3}, seed=1)
    >>> processor.preprocess(df)
       column
    0     0.0
    1     0.0
    2     0.0
    >>> avatar = pd.DataFrame(np.ones(3), columns=["column"], dtype="float")
    >>> avatar
       column
    0     1.0
    1     1.0
    2     1.0

    The post process reduces the gap between df and avatar

    >>> processor.postprocess(df, avatar)
       column
    0     0.3
    1     0.3
    2     0.3
    """

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
        """Preprocess is doing nothing."""
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Force to reduce the difference between originals and avatars."""
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
