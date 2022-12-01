from typing import List, Optional

import pandas as pd


class RelativeDifferenceProcessor:
    def __init__(
        self,
        target: str,
        references: List[str],
        scaling_unit: Optional[int] = None,
        target_rename: Optional[str] = None,
        drop_original_target: Optional[bool] = False,
    ):
        r"""Processor to express numeric variables as a difference relative to the sum of other variables.

        Arguments
        ---------
            target: variables to transform
            references: the variable of reference
            target_rename: target name after preprocess.
            scaling_unit: divide difference by factor to handle unit variation.
              Eg. if 1000, a difference in meters will be expressed in kilometers.
            drop_original_target: drop original_target. Can only be set to ``True``
                if ``target_rename`` is specified
        """
        self.target = target
        self.references = references
        self.scaling_unit = scaling_unit or 1
        if drop_original_target and target_rename is None:
            raise ValueError(
                "Expected drop_original_target to be False if a target_rename is None, "
                f"got {drop_original_target} instead",
            )
        self.target_rename = target_rename
        if self.target_rename is None:
            self.target_rename = self.target
        self.drop_original_target = drop_original_target

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform a numeric variable into a difference relative to the sum of other variables.

        Arguments
        ---------
            df: dataframe to transform

        Returns
        -------
            a dataframe with the transformed version of wanted columns
        """
        df = df.copy()

        wrong_variables = set(self.references) - set(df.columns.values)
        if wrong_variables:
            raise ValueError(
                "Expected all reference variables in dataset columns, "
                f"got {wrong_variables} instead."
            )
        df[self.target_rename] = (
            df[self.target].sub(df[self.references].sum(axis=1))
        ) / self.scaling_unit
        if self.drop_original_target:
            df = df.drop(columns=[self.target])
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Transform a difference relative to the sum of other variables into an absolute numeric value.

        Arguments
        ---------
            source: not used
            dest: dataframe to transform

        Returns
        -------
            a dataframe with the transformed version of wanted columns
        """
        dest = dest.copy()
        wrong_variables = set(self.references) - set(dest.columns.values)
        if wrong_variables:
            raise ValueError(
                "Expected all reference variables in dataset columns, "
                f"got {wrong_variables} instead."
            )
        dest[self.target] = (dest[self.target_rename] * self.scaling_unit).add(
            dest[self.references].sum(axis=1)
        )
        return dest
