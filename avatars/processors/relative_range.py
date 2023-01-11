from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd
from numpy.random import SeedSequence


class RelativeRangeProcessor:
    """Processor to express a numeric variables as within a range defined by two other variables.

    Arguments
    ---------
        target:
            variable to transform
        bounds:
            the variables defining the upper and lower bounds

    Keyword Arguments
    -----------------
        drop_target:
            set to ``True`` to drop the target variable at preprocess step.
        drop_references:
            set to ``True`` to drop the reference variables at postprocess step.
            default: ``False``
        seed:
            the randomness seed

    Examples
    --------
    >>> df = pd.DataFrame(
    ...    {
    ...        "variable_1": [130, 230, 200],
    ...        "variable_1_lb": [110, 180, 130],
    ...        "variable_1_ub": [210, 340, 280],
    ...    }
    ... )
    >>> processor = RelativeRangeProcessor(
    ...    target="variable_1", bounds=("variable_1_lb", "variable_1_ub"), drop_references=True
    ...    )
    >>> df = processor.preprocess(df)
    >>> df
        variable_1_lb  variable_1_ub
    0            110            210
    1            180            340
    2            130            280

    TODO : finish this processor with oliv
    """

    def __init__(
        self,
        target: str,
        bounds: Tuple[str, str],
        drop_target: bool = True,
        drop_references: bool = False,
        seed: Optional[Union[int, SeedSequence]] = None,
    ):
        self.target = target
        self.bounds = bounds
        self.drop_references = drop_references
        self.drop_target = drop_target
        self.seed = seed

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Set a numeric variable as within a range defined by two other variables.

        Arguments
        ---------
            df: dataframe to transform

        Returns
        -------
            DataFrame: a dataframe with the transformed version of wanted columns
        """
        df = df.copy()

        wrong_variables = set(self.bounds) - set(df.columns.values)
        if wrong_variables:
            raise ValueError(
                f"Expected all bounds variables in dataset columns, got {wrong_variables} instead."
            )

        if self.drop_target:
            df = df.drop(columns=[self.target])
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Sample values for the target variable within the range defined.

        Arguments
        ---------
            source: not used
            dest: dataframe to transform

        Returns
        -------
            DataFrame: a dataframe with the transformed version of wanted columns
        """
        dest = dest.copy()
        random_gen = np.random.default_rng(self.seed)

        # Set current target values as None if the target was removed
        if self.target not in dest.columns:
            dest[self.target] = np.full(dest.shape[0], None)

        # Sample target value where there is no value or where current value is out of bound
        dest[self.target] = [
            random_gen.uniform(np.minimum(r0, r1), np.maximum(r0, r1))
            if not np.isnan(r0)
            and not np.isnan(r1)
            and (
                val is None
                or not ((val >= np.minimum(r0, r1)) and (val <= np.maximum(r0, r1)))
            )
            else val
            if not np.isnan(r0) and not np.isnan(r1)
            else np.nan
            for r0, r1, val in zip(
                dest[self.bounds[0]], dest[self.bounds[1]], dest[self.target]
            )
        ]

        if self.drop_references:
            dest = dest.drop(columns=[x for x in self.bounds])
        return dest
