from typing import List

import numpy as np
import pandas as pd

from avatars.lib.saferound import saferound


class ProportionProcessor:
    """Processor to express numeric variables as a proportion of another variable.

    By this transformation, we keep the addition and subtraction relations
    such as variable_1 = variable_2 + variable_3.

    Arguments
    ---------
        variable_names:
            variables to transform
        reference:
            the variable of reference

    Keyword Arguments
    -----------------
        sum_to_one:
            set to True to ensure the sum of the variables sum to 1 once transformed.
            default: True
        decimal_count:
            the number of decimals postprocessed variables should have

    Examples
    --------
    >>> df =  pd.DataFrame(
    ...        {
    ...            "variable_1": [100, 10],
    ...            "variable_2": [10, 10],
    ...            "variable_3": [90, 30],
    ...        }
    ...    )
    >>> processor = ProportionProcessor(
    ...    variable_names=["variable_2", "variable_3"],
    ...    reference="variable_1",
    ... )
    >>> processor.preprocess(df=df)
       variable_1  variable_2  variable_3
    0         100        0.10        0.90
    1          10        0.25        0.75

    This processor allows you to transform some variable as a proportion of another variable.
    By default, the processor enforces the proportion of `variable_names` to be equal to 1.

    >>> avatar = pd.DataFrame(
    ...        {
    ...            "variable_1": [60, 15],
    ...            "variable_2": [0.15, 0.88],
    ...            "variable_3": [0.18, 0.77],
    ...        }
    ...    )
    >>> avatar
       variable_1  variable_2  variable_3
    0          60        0.15        0.18
    1          15        0.88        0.77

    Then the postprocess allows you to get the original variable unit.

    >>> processor.postprocess(df, avatar)
       variable_1  variable_2  variable_3
    0          60        27.3        32.7
    1          15         8.0         7.0

    By this, we keep the mathematical relation variable_1 = variable_2 + variable_3

    with `sum_to_one=False`

    >>> processor = ProportionProcessor(
    ...    variable_names=["variable_2", "variable_3"],
    ...    reference="variable_1",
    ...    sum_to_one=False,
    ... )
    >>> processor.preprocess(df=df)
       variable_1  variable_2  variable_3
    0         100         0.1         0.9
    1          10         1.0         3.0
    >>> avatar = pd.DataFrame(
    ...        {
    ...            "variable_1": [60, 15],
    ...            "variable_2": [0.15, 0.88],
    ...            "variable_3": [1.5, 2.8],
    ...        }
    ...    )
    >>> avatar
       variable_1  variable_2  variable_3
    0          60        0.15         1.5
    1          15        0.88         2.8
    >>> processor.postprocess(df, avatar)
       variable_1  variable_2  variable_3
    0          60         9.0        90.0
    1          15        13.2        42.0
    """

    def __init__(
        self,
        variable_names: List[str],
        reference: str,
        *,
        sum_to_one: bool = True,
        decimal_count: int = 1,
    ):
        self.variable_names = variable_names
        self.reference = reference
        self.sum_to_one = sum_to_one
        self.decimal_count = decimal_count

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform numeric variables into proportion of another variable.

        If some values for the variables to transform are set to nan, they will be transformed
        into nan and will be considered as a 0% proportion of the reference when transforming
        values of other variables.

        Arguments
        ---------
            df: dataframe to transform

        Returns
        -------
            DataFrame: a dataframe with the transformed version of wanted columns
        """
        col_order = df.columns
        df = df.copy()
        if self.reference not in df.columns.values:
            raise ValueError(
                "variable_name",
                f"variable {self.reference} cannot be found in the dataframe variables",
            )
        if self.sum_to_one:
            sub_df = df[self.variable_names].div(
                df[self.variable_names].sum(axis=1), axis=0
            )
        else:
            sub_df = df[self.variable_names].div(df[self.reference], axis=0)

        # Ensure that target variables that were set to zero remain at zero
        for variable in self.variable_names:
            zero_indices = df[df[variable] == 0].index
            if len(zero_indices) > 0:
                sub_df.loc[zero_indices, variable] = 0

        df = df.drop(columns=self.variable_names)
        df = pd.concat([df, sub_df], axis=1)[col_order]
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Transform proportion of another variable into an absolute numeric value.

        Arguments
        ---------
            source: not used
            dest: dataframe to transform

        Returns
        -------
            DataFrame: a dataframe with the transformed version of wanted columns
        """
        col_order = dest.columns
        dest = dest.copy()
        if self.reference not in dest.columns.values:
            raise ValueError(
                "variable_name",
                f"variable {self.reference} cannot be found in the dataframe variables",
            )
        if self.sum_to_one:
            sub_df = (
                dest[self.variable_names]
                .mul(dest[self.reference], axis=0)
                .div(dest[self.variable_names].sum(axis=1), axis=0)
            )
        else:
            sub_df = dest[self.variable_names].mul(dest[self.reference], axis=0)
        dest = dest.drop(columns=self.variable_names)
        dest = pd.concat([dest, sub_df], axis=1)[col_order]

        # Perform rounding of the postprocess variable to the expected number of decimals.
        # We use saferounding here to force the sum of rounded variables to remain unchanged.
        if not self.sum_to_one:
            return dest

        for i, row in enumerate(dest[self.variable_names].values):
            if not np.any(np.isnan(row)):
                dest.loc[i, self.variable_names] = saferound(
                    row.tolist(), self.decimal_count
                )

        return dest
