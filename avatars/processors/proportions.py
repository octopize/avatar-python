from typing import List

import pandas as pd
import numpy as np
from avatars.lib.saferound import saferound

class ProportionProcessor:
    def __init__(
        self, variable_names: List[str], reference: str, sum_to_one: bool = True, decimal_count: int = 1
    ):
        """Processor to express numeric variables as proportion of another variable.

        Arguments
        ---------
            variable_names: variables to transform
            reference: the variable of reference
            sum_to_one: set to True to ensure the sum of the variables sum to 1 once transformed.
                default: True
            decimal_count: the number of decimals postprocessed variables should have
        """
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
        # We use saferounding here to force the sum of rounded variables to remain unchanged. 
        if self.sum_to_one:
            for i, row in enumerate(dest[self.variable_names].values):
                if not np.any(np.isnan(row)):
                    dest.loc[i, self.variable_names] = saferound(row, self.decimal_count)
        return dest
