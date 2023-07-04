from typing import Optional

import numpy as np
import pandas as pd


class InterRecordBoundedRangeDifferenceProcessor:
    """Processor to express two related bounded variables relative to previous records.

    This processor can be used only on data where there are several records for each individual.
    By this transformation, variables such as `var_a` and `var_b` whose values are cumulative over
    successive records `t` in the following way:
    var_a_t <= var_b_t <= var_a_t+1 <= var_b_t+1 <= var_a_t+2 ...

    will be expressed as:
    - a variable containing the first value of `var_a`.
    - a variable containing the difference from the previous record
    - a variable containing the range between the start and end variables

    Difference and range variables are expressed as proportion of possible change between the
    value and the bound (upper or lower). For example, for a variable whose value only spreads from
    10 (lower bound) to 100 (upper bound), if the previous records value is 60 and the new value
    is 30, the proportion will be calculated as (30 - 60) / (60 - 10) = -0.6

    This processor is not suitable for data where any of the variables passed as args contain
    missing values.

    Keyword Arguments
    -----------------
        id_variable:
            variable indicating which individual each row belongs to
        target_start_variable:
            variable representing the start of the range to transform
        target_end_variable:
            variable representing the end of the range to transform
        sort_by_variable:
            variable used to sort records for each id
        new_first_variable:
            name of the variable to be created to contain the first value of the target variable
        new_range_variable:
            name of the variable to be created to contain the range value
        new_difference_variable:
            name of the variable to be created to contain the difference value
        should_round_output:
            set to True to force post-processed values to be integer.

    Examples
    --------
    >>> df = pd.DataFrame(
    ...    {
    ...       'quantity_start': [30, 100, 80, 70, 40, 70],
    ...       'quantity_end': [10, 80, 70, 60, 30, 5],
    ...       'b': [4, 3, 0, 0, 2, 4],
    ...       'id': [1,1,1,2,2,2]
    ...    }
    ... )
    >>> processor = InterRecordBoundedRangeDifferenceProcessor(
    ...    id_variable='id',
    ...    target_start_variable='quantity_start',
    ...    target_end_variable='quantity_end',
    ...    new_first_variable_name='quantity_s_first_val',
    ...    new_difference_variable_name="quantity_diff_to_bound",
    ...    new_range_variable="quantity_range",
    ...    should_round_output=True
    ... )
    >>> preprocessed_df = processor.preprocess(df)
    >>> print(preprocessed_df)
       b  id  quantity_range  quantity_s_first_val  quantity_diff_to_bound
    0  4   1       -0.800000                    30                0.000000
    1  3   1       -0.210526                    30                1.000000
    2  0   1       -0.133333                    30                0.000000
    3  0   2       -0.153846                    70                0.000000
    4  2   2       -0.285714                    70               -0.363636
    5  4   2       -1.000000                    70                0.571429

    The postprocess allows you to transform some preprocessed data back into its original format.

    >>> processor.postprocess(df, preprocessed_df)
       quantity_start  quantity_end  b  id
    0              30            10  4   1
    1             100            80  3   1
    2              80            70  0   1
    3              70            60  0   2
    4              40            30  2   2
    5              70             5  4   2
    """

    def __init__(
        self,
        *,
        id_variable: str,
        target_start_variable: str,
        target_end_variable: str,
        new_first_variable_name: str,
        new_range_variable: str,
        new_difference_variable_name: str,
        sort_by_variable: Optional[str] = None,
        should_round_output: bool = True,
    ):
        self.id_variable = id_variable
        self.target_start_variable = target_start_variable
        self.target_end_variable = target_end_variable
        self.new_first_variable_name = new_first_variable_name
        self.new_range_variable = new_range_variable
        self.new_difference_variable_name = new_difference_variable_name
        self.sort_by_variable = sort_by_variable
        self.should_round_output = should_round_output

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        variables_to_check = [
            self.id_variable,
            self.target_start_variable,
            self.target_end_variable,
        ]
        if self.sort_by_variable:
            variables_to_check.append(self.sort_by_variable)
        if len(set(variables_to_check).difference(df.columns.values)) > 0:
            msg = "Expected valid variable names for `id_variable`, `target_start_variable`, "
            msg += f"`target_end_variable` and `sort_by_variable`, got '{self.id_variable}',"
            msg += f" '{self.target_start_variable}', '{self.target_end_variable}' and "
            msg += f"'{self.sort_by_variable}' instead"
            raise ValueError(msg)
        if df[variables_to_check].isnull().values.any():
            msg = "Expected no missing values for `id_variable`, `target_start_variable`, "
            msg += "`target_end_variable` and `sort_by_variable`, "
            msg += "got columns with nulls instead"
            raise ValueError(msg)

        working = df.copy()

        # sort records for each individual
        if self.sort_by_variable:
            working = working.sort_values([self.id_variable, self.sort_by_variable])
        else:
            working = working.sort_values([self.id_variable])

        # determine lb and ub
        working["lb"] = min(
            min(working[self.target_start_variable]),
            min(working[self.target_end_variable]),
        )
        working["ub"] = max(
            max(working[self.target_start_variable]),
            max(working[self.target_end_variable]),
        )

        # compute relative range to ub or lb
        working["range_increase"] = (
            working[self.target_end_variable] >= working[self.target_start_variable]
        )
        working["range_decrease"] = (
            working[self.target_end_variable] < working[self.target_start_variable]
        )
        working["diff_to_lb"] = abs(working[self.target_start_variable] - working["lb"])
        working["diff_to_ub"] = abs(working[self.target_start_variable] - working["ub"])
        working["relative_range_to_lb"] = (
            -abs(
                working[self.target_end_variable] - working[self.target_start_variable]
            )
            / working["diff_to_lb"]
        )
        working["relative_range_to_lb"] = working["relative_range_to_lb"].replace(
            [np.inf, -np.inf, np.nan], 0
        )
        working["relative_range_to_ub"] = (
            abs(working[self.target_end_variable] - working[self.target_start_variable])
            / working["diff_to_ub"]
        )
        working["relative_range_to_ub"] = working["relative_range_to_ub"].replace(
            [np.inf, -np.inf, np.nan], 0
        )
        working[self.new_range_variable] = (
            working["range_decrease"] * working["relative_range_to_lb"]
            + working["range_increase"] * working["relative_range_to_ub"]
        )

        # compute first value
        working[self.new_first_variable_name] = working.groupby(self.id_variable)[
            self.target_start_variable
        ].transform("first")

        # compute difference from previous val as proportion to lb or ub
        working["previous_val"] = working.groupby(self.id_variable)[
            self.target_end_variable
        ].shift()
        working = working.reset_index(drop=False)
        working.loc[working["previous_val"].isnull(), "previous_val"] = working[
            self.target_start_variable
        ]  # for first record, set previous value as same value to avoid NaN
        working["increase"] = (
            working[self.target_start_variable] >= working["previous_val"]
        )
        working["decrease"] = (
            working[self.target_start_variable] < working["previous_val"]
        )
        working["diff_to_lb"] = abs(working["previous_val"] - working["lb"])
        working["diff_to_ub"] = abs(working["previous_val"] - working["ub"])
        working["relative_diff_to_lb"] = (
            -abs(working[self.target_start_variable] - working["previous_val"])
            / working["diff_to_lb"]
        )
        working["relative_diff_to_lb"] = working["relative_diff_to_lb"].replace(
            [np.inf, -np.inf, np.nan], 0
        )
        working["relative_diff_to_ub"] = (
            abs(working[self.target_start_variable] - working["previous_val"])
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
                self.target_start_variable,
                self.target_end_variable,
            ]
        )
        working = working.drop(
            columns=[
                "range_increase",
                "range_decrease",
                "relative_range_to_lb",
                "relative_range_to_ub",
            ]
        )

        # Re-order data as it was in the input - required because of earlier sorting step
        working = working.set_index("index").sort_index()
        working.index.name = None

        return working

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        working = dest.copy()
        vals_s = []
        vals_e = []

        working["original_order"] = range(len(working))
        working = working.sort_values(by=[self.id_variable])

        # determine lb and ub
        lb = min(
            min(source[self.target_start_variable]),
            min(source[self.target_end_variable]),
        )
        ub = max(
            max(source[self.target_start_variable]),
            max(source[self.target_end_variable]),
        )

        # identify whether the difference and range values have increased or decreased
        working["increase"] = working[self.new_difference_variable_name] >= 0
        working["decrease"] = ~working["increase"]
        working[self.new_difference_variable_name] = abs(
            working[self.new_difference_variable_name]
        )
        working["range_increase"] = working[self.new_range_variable] >= 0
        working["range_decrease"] = ~working["range_increase"]

        # Iteratively compute the values based on the values of previous records
        # NB: It is not clear how this could be vectorized
        for theid in working[self.id_variable].unique():
            previous_val = working[working[self.id_variable] == theid][
                self.new_first_variable_name
            ].values[0]
            for (
                increase,
                decrease,
                relative_diff_to_bound,
                range_diff,
                range_increase,
                range_decrease,
            ) in working.loc[
                working[self.id_variable] == theid,
                [
                    "increase",
                    "decrease",
                    self.new_difference_variable_name,
                    self.new_range_variable,
                    "range_increase",
                    "range_decrease",
                ],
            ].values:
                val_s = (
                    previous_val
                    - decrease * (relative_diff_to_bound * abs(previous_val - lb))
                    + increase * (relative_diff_to_bound * abs(previous_val - ub))
                )
                val_e = (
                    val_s
                    + range_decrease * (range_diff * abs(val_s - lb))
                    + range_increase * (range_diff * abs(val_s - ub))
                )
                previous_val = val_e
                vals_s.append(val_s)
                vals_e.append(val_e)
        working[self.target_start_variable] = vals_s
        working[self.target_end_variable] = vals_e

        # optional rounding step
        if self.should_round_output:
            working[self.target_start_variable] = working[
                self.target_start_variable
            ].astype(int)
            working[self.target_end_variable] = working[
                self.target_end_variable
            ].astype(int)

        working = working.sort_values(by=["original_order"])

        # remove tmp variables
        columns_to_remove = [
            "increase",
            "decrease",
            self.new_difference_variable_name,
            self.new_first_variable_name,
            self.new_range_variable,
            "range_increase",
            "range_decrease",
            "original_order",
        ]
        working = working.drop(columns=columns_to_remove)

        # order columns
        common_cols = [c for c in source.columns if c in working.columns]
        other_cols = [c for c in working.columns if c not in source.columns]
        cols_order = common_cols + other_cols
        working = working[cols_order]

        return working
