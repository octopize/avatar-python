import numpy as np
import pandas as pd


class InterRecordBoundedCumulatedDifferenceProcessor:
    """Processor to express the value of a variable as the difference from the previous value.

    This processor can be used only on data where there are several records for each individual.
    By this transformation, a variable whose value is cumulative will be expressed as:
    - a variable containing its first value.
    - a variable containing the difference from the previous record

    The difference variable is expressed as the proportion of possible change between the
    value and the bound (upper or lower). For example, for a variable whose value only spreads from
    10 (lower bound) to 100 (upper bound), if the previous records value is 60 and the new value
    is 30, the proportion will be calculated as (30 - 60) / (60 - 10) = -0.6. this ensures that
    bounds are respected during the pre-processing and post-processing of the data.

    This processor is not suitable for data where the target or the id variable contain missing
    values.

    Keyword Arguments
    -----------------
        id_variable:
            variable indicating which individual each row belongs to
        target_variable:
            variable to transform
        new_first_variable_name:
            name of the variable to be created to contain the first value of the target variable
        new_difference_variable_name:
            name of the variable to be created to contain the difference value
        should_round_output:
            set to `True` to force post-processed values to be integers.
    Examples
    --------
    >>> df = pd.DataFrame({
    ...    "id": [1, 2, 1, 1, 2, 2],
    ...    "value": [1025, 20042, 1000, 1130, 20000, 20040],
    ... })
    >>> processor = InterRecordBoundedCumulatedDifferenceProcessor(
    ...    id_variable='id',
    ...    target_variable='value',
    ...    new_first_variable_name='first_value',
    ...    new_difference_variable_name='difference_to_bound',
    ...    should_round_output=True
    ...    )
    >>> processor.preprocess(df)
       id  first_value  difference_to_bound
    0   1         1025             0.000000
    1   2        20042             0.000000
    2   1         1025            -1.000000
    3   1         1025             0.006827
    4   2        20042            -0.002206
    5   2        20042             0.952381

    The postprocess allows you to transform some preprocessed data back into its original format

    >>> preprocessed_df = pd.DataFrame({
    ...    "id": [1, 2, 1, 1, 2, 2],
    ...    "first_value": [1025, 20042, 1025, 1025, 20042, 20042],
    ...    "difference_to_bound": [0, 0, -1, 0.006827, -0.002206, 0.952381],
    ... })
    >>> processor.postprocess(df, preprocessed_df)
       id  value
    0   1   1025
    1   2  20042
    2   1   1000
    3   1   1130
    4   2  20000
    5   2  20040
    """

    def __init__(
        self,
        id_variable: str,
        target_variable: str,
        new_first_variable_name: str,
        new_difference_variable_name: str,
        should_round_output: bool = False,
    ):
        self.id_variable = id_variable
        self.target_variable = target_variable
        self.new_first_variable_name = new_first_variable_name
        self.new_difference_variable_name = new_difference_variable_name
        self.round_output = should_round_output

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.id_variable not in df.columns.values:
            raise ValueError(
                f"Expected a valid `id_variable`, got {self.id_variable} instead"
            )

        if self.target_variable not in df.columns.values:
            raise ValueError(
                f"Expected a valid `target_variable`, got {self.target_variable} instead"
            )

        if df[self.id_variable].isnull().values.any():
            raise ValueError(
                "Expected no missing values for id variable, got column with nulls instead"
            )

        if df[self.target_variable].isnull().values.any():
            raise ValueError(
                "Expected no missing values for target variable, got column with nulls instead"
            )

        working = df.copy()

        # determine lb and ub
        working["lb"] = min(working[self.target_variable])
        working["ub"] = max(working[self.target_variable])

        # store first value of target variable
        working[self.new_first_variable_name] = working.groupby(self.id_variable)[
            self.target_variable
        ].transform("first")

        # store the difference between current and previous value
        working["previous_val"] = working.groupby(self.id_variable)[
            self.target_variable
        ].shift()
        working = working.reset_index(drop=True)
        working.loc[working["previous_val"].isnull(), "previous_val"] = working[
            self.target_variable
        ]  # for first record, set previous value as same value to avoid NaN

        # compute difference from previous val as proportion to lb or ub
        working["increase"] = working[self.target_variable] >= working["previous_val"]
        working["decrease"] = working[self.target_variable] < working["previous_val"]
        working["diff_to_lb"] = abs(working["previous_val"] - working["lb"])
        working["diff_to_ub"] = abs(working["previous_val"] - working["ub"])
        working["relative_diff_to_lb"] = (
            -abs(working[self.target_variable] - working["previous_val"])
            / working["diff_to_lb"]
        )
        working["relative_diff_to_lb"] = working["relative_diff_to_lb"].replace(
            [np.inf, -np.inf, np.nan], 0
        )
        working["relative_diff_to_ub"] = (
            abs(working[self.target_variable] - working["previous_val"])
            / working["diff_to_ub"]
        )
        working["relative_diff_to_ub"] = working["relative_diff_to_ub"].replace(
            [np.inf, -np.inf, np.nan], 0
        )

        working[self.new_difference_variable_name] = (
            working["decrease"] * working["relative_diff_to_lb"]
            + working["increase"] * working["relative_diff_to_ub"]
        )

        # Remove tmp variables
        working = working.drop(
            columns=[
                "relative_diff_to_lb",
                "relative_diff_to_ub",
                "previous_val",
                "diff_to_lb",
                "diff_to_ub",
                "decrease",
                "increase",
                "lb",
                "ub",
            ]
        )

        # Remove original variables
        working = working.drop(columns=[self.target_variable])

        return working

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        if self.new_first_variable_name not in dest.columns.values:
            raise ValueError(
                "Expected a valid `new_first_variable_name`, "
                f"got {self.new_first_variable_name} instead"
            )

        if self.new_difference_variable_name not in dest.columns.values:
            raise ValueError(
                "Expected a valid `new_difference_variable_name`, "
                f"got {self.new_difference_variable_name} instead"
            )

        if source[self.id_variable].isnull().values.any():
            raise ValueError(
                "Expected no missing values for id variable in source, "
                "got column with nulls instead"
            )

        if source[self.target_variable].isnull().values.any():
            raise ValueError(
                "Expected no missing values for target variable in source, "
                "got column with nulls instead"
            )

        if dest[self.new_difference_variable_name].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `new_difference_variable_name`, "
                "got column with nulls instead"
            )

        if dest[self.new_first_variable_name].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `new_first_variable_name`, "
                "got column with nulls instead"
            )

        working = dest.copy()

        vals = []
        sorted_indices = []

        # determine lb and ub
        lb = min(source[self.target_variable])
        ub = max(source[self.target_variable])

        # identify whether the difference and range values have increased or decreased
        working["increase"] = working[self.new_difference_variable_name] >= 0
        working["decrease"] = ~working["increase"]
        working[self.new_difference_variable_name] = abs(
            working[self.new_difference_variable_name]
        )

        # Iteratively compute the values based on the values of previous records
        # NB: It is not clear how this could be vectorized
        for theid in working[self.id_variable].unique():
            selected_indices = working[working[self.id_variable] == theid].index
            previous_val = working[working[self.id_variable] == theid][
                self.new_first_variable_name
            ].values[0]
            for increase, decrease, relative_diff_to_bound in working.loc[
                working[self.id_variable] == theid,
                ["increase", "decrease", self.new_difference_variable_name],
            ].values:
                val = (
                    previous_val
                    - decrease * (relative_diff_to_bound * abs(previous_val - lb))
                    + increase * (relative_diff_to_bound * abs(previous_val - ub))
                )
                previous_val = val
                vals.append(val)
            sorted_indices.extend(selected_indices)

        vals = [vals[x] for x in np.argsort(sorted_indices)]

        working[self.target_variable] = vals

        # optional rounding step
        if self.round_output:
            working[self.target_variable] = (
                working[self.target_variable].round(0).astype(int)
            )

        # remove tmp variables
        working = working.drop(
            columns=[
                "increase",
                "decrease",
                self.new_difference_variable_name,
                self.new_first_variable_name,
            ]
        )

        return working
