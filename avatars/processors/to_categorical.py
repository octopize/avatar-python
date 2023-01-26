from typing import List

import numpy as np
import pandas as pd


class ToCategoricalProcessor:
    def __init__(
        self,
        variables: List[str],
        *,
        keep_continuous: bool = False,
        continuous_suffix: str = "__cont",
        category: str = "other",
    ):
        """Processor to model selected numeric variables as categorical variables.

        Arguments
        ---------
            variables:
                Continuous variables to transform to categorical

        Keyword Arguments
        -----------------
            keep_continuous:
                if `True`, continuous variables will be kept and
            suffixed with `continuous_suffix`.
            continuous_suffix:
                suffix for the continuous variable created during preprocess.
            category:
                if `keep_continuous=True`, name of the new category, needed for some specific
                avatarization cases with the use of group_modalities processor

        Examples
        --------
        """
        self.variables = variables
        self.keep_continuous = keep_continuous
        self.continuous_suffix = continuous_suffix
        self.category = category

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform numeric variables into categorical variables.

        Arguments
        ---------
            df: dataframe to transform

        Returns
        -------
            DataFrame: transformed dataframe
        """
        unknown_variables = [elem for elem in self.variables if elem not in df.columns]
        if unknown_variables:
            raise ValueError(
                "Expected variables in DataFrame, " f"got {unknown_variables} instead.",
            )
        df = df.copy()

        # Perform the transformation by creating a new column cont_suffix where
        # NAs are kept as NAs.
        if self.keep_continuous:
            self.continuous_variables = [
                x + self.continuous_suffix for x in self.variables
            ]
            df[self.continuous_variables] = df[self.variables]

        df[self.variables] = df[self.variables].astype("object")
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Transform converted categorical variables back to numeric.

        Arguments
        ---------
            source: reference data frame
            dest: data frame to transform

        Returns
        -------
            DataFrame: transformed data frame
        """
        dest = dest.copy()

        # affect the continuous value to modality "category",
        # needed for some specific avatarization cases with the use of group_modalities processor
        if self.keep_continuous:
            dest[self.variables] = np.where(
                dest[self.variables] == self.category,
                dest[self.continuous_variables],
                dest[self.variables],
            )
            dest = dest.drop(columns=self.continuous_variables)

        # reassign the original data type
        dest[self.variables] = dest[self.variables].astype(
            source[self.variables].dtypes.to_dict()
        )

        return dest
