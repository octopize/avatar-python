from typing import List, Optional

import pandas as pd


class RelativeDifferenceProcessor:
    """Express numeric variables as a difference relative to the sum of other variables.

    Even if the avatarization is keeping relation and correlation,
    it will not guarantee mathematical relation retention.
    You can apply the RelativeDifferenceProcessor to retain this relation between variables.

    Arguments
    ---------
        target:
            variables to transform
        references:
            the variable of reference

    Keyword Arguments
    -----------------
        scaling_unit:
            divide difference by factor to handle unit variation.
            Eg. if scaling_unit=1000, a difference in meters will be expressed in kilometers.
        target_rename:
            target name after preprocess.
        drop_original_target:
            drop original_target. Can only be set to ``True``
            if ``target_rename`` is specified

    Examples
    --------
    >>> import numpy as np
    >>> df = pd.DataFrame(
    ...    {
    ...        "variable_1": [100, 150, 120, 100],
    ...        "variable_2": [110, 180, 130, np.nan]
    ...        }
    ...    )
    >>> processor = RelativeDifferenceProcessor(target="variable_2", references=["variable_1"])
    >>> df = processor.preprocess(df)
    >>> df
       variable_1  variable_2
    0         100        10.0
    1         150        30.0
    2         120        10.0
    3         100         NaN

    This preprocess allows you to convert some variable as a difference of other. It can useful
    when there is a relation between variables when `variable_2 >= variable_1`

    >>> avatar = pd.DataFrame(
    ...    {
    ...        "variable_1": [110, 105, 115, 107],
    ...        "variable_2": [12, np.nan, 23, 15],
    ...        }
    ...    )
    >>> avatar
       variable_1  variable_2
    0         110        12.0
    1         105         NaN
    2         115        23.0
    3         107        15.0
    >>> avatar = processor.postprocess(df, avatar)
    >>> avatar
       variable_1  variable_2
    0         110       122.0
    1         105         NaN
    2         115       138.0
    3         107       122.0

    This processor can be useful when you have a relation between three variables.
    Lets suppose you have three variable with such as:

    - age_at_t0
    - age_at_t1
    - age_at_t2

    The relation is age_at_t0 < age_at_t1 < age_at_t2, for all the individuals.

    >>> df = pd.DataFrame(
    ...    {
    ...        "age_at_t0": [20, 40, 34, 56],
    ...        "age_at_t1": [23, 46, 37, 57],
    ...        "age_at_t2": [29, 54, 39, 64],
    ...        }
    ...    )
    >>> df
       age_at_t0  age_at_t1  age_at_t2
    0         20         23         29
    1         40         46         54
    2         34         37         39
    3         56         57         64
    >>> processor_1 = RelativeDifferenceProcessor( target="age_at_t2", references=["age_at_t1"])
    >>> processor_2 = RelativeDifferenceProcessor( target="age_at_t1", references=["age_at_t0"])

    .. note::

        Be careful about the order of application of the processors

    >>> processed = processor_1.preprocess(df)
    >>> processor_2.preprocess(processed)
       age_at_t0  age_at_t1  age_at_t2
    0         20        3.0        6.0
    1         40        6.0        8.0
    2         34        3.0        2.0
    3         56        1.0        7.0

    >>> avatar = pd.DataFrame(
    ...    {
    ...        "age_at_t0": [22, 38, 34, 56],
    ...        "age_at_t1": [4.0, 5.0, 1.0, 5.0],
    ...        "age_at_t2": [5.0, 3.0, 7.0, 6.0],
    ...        }
    ...    )
    >>> avatar
       age_at_t0  age_at_t1  age_at_t2
    0         22        4.0        5.0
    1         38        5.0        3.0
    2         34        1.0        7.0
    3         56        5.0        6.0
    >>> post_avatar = processor_2.postprocess(df, avatar)
    >>> processor_1.postprocess(df, post_avatar)
       age_at_t0  age_at_t1  age_at_t2
    0         22       26.0       31.0
    1         38       43.0       46.0
    2         34       35.0       42.0
    3         56       61.0       67.0
    """

    def __init__(
        self,
        target: str,
        references: List[str],
        scaling_unit: Optional[int] = None,
        target_rename: Optional[str] = None,
        drop_original_target: Optional[bool] = False,
    ):
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
        if df[self.references].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `references`, "
                "got column with missing values instead"
            )
        df[self.target_rename] = (
            df[self.target].sub(df[self.references].sum(axis=1))
        ) / self.scaling_unit
        if self.drop_original_target:
            df = df.drop(columns=[self.target])
        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Transform a difference relative to the sum of variables into an absolute numeric value.

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
