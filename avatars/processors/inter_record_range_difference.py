import pandas as pd


class InterRecordRangeDifferenceProcessor:
    """Processor to express the values of two related variables relative to previous records.

    This processor can be used only on data where there are several records for each individual.
    By this transformation, variables such as `var_a` and `var_b` whose values are cumulative over
    successive records `t` in the following way:
    var_a_t <= var_b_t <= var_a_t+1 <= var_b_t+1 <= var_a_t+2 ...

    will be expressed as:
    - a variable containing the first value of `var_a`.
    - a variable containing the difference from the previous record (i.e. `var_a_t` - `var_b_t-1`)
    - a variable containing the range between the start and end variables
    (i.e. `var_b_t` - `var_a_t`)

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
        sort_by_variable_name:
            variable used to sort records for each id
        new_first_variable_name:
            name of the variable to be created to contain the first value of the target variable
        new_range_variable_name:
            name of the variable to be created to contain the range value
        new_difference_variable_name:
            name of the variable to be created to contain the difference value

    Examples
    --------
    >>> df = pd.DataFrame(
    ...     {
    ...         "id": [1, 2, 1, 1, 2, 2],
    ...         "start": [7, 14, 6, 12, 10, 23],
    ...         "end": [8, 18, 7, 15, 12, 24],
    ...     }
    ... )
    >>> processor = InterRecordRangeDifferenceProcessor(
    ...     id_variable="id",
    ...     target_start_variable='start',
    ...     target_end_variable='end',
    ...     sort_by_variable_name="start",
    ...     new_first_variable_name="first_value",
    ...     new_range_variable_name='range_value',
    ...     new_difference_variable_name="value_difference",
    ... )
    >>> processor.preprocess(df)
        id  range_value  first_value  value_difference
    0   1            1            6               0.0
    1   2            4           10               2.0
    2   1            1            6               0.0
    3   1            3            6               4.0
    4   2            2           10               0.0
    5   2            1           10               5.0

    The postprocess allows you to transform some preprocessed data back into its original format

    >>> preprocessed_df = pd.DataFrame(
    ...     {
    ...         "id": [1, 2, 1, 1, 2, 2],
    ...         "range_value": [1, 4, 1, 3, 2, 1],
    ...         "first_value": [6, 10, 6, 6, 10, 10],
    ...         "value_difference": [0, 2, 0, 4, 0, 5],
    ...     }
    ... )
    >>> processor.postprocess(df, preprocessed_df)
        id  start   end
    0   1    7.0   8.0
    1   2   14.0  18.0
    2   1    6.0   7.0
    3   1   12.0  15.0
    4   2   10.0  12.0
    5   2   23.0  24.0
    """

    def __init__(
        self,
        *,
        id_variable: str,
        target_start_variable: str,
        target_end_variable: str,
        sort_by_variable_name: str,
        new_first_variable_name: str,
        new_range_variable_name: str,
        new_difference_variable_name: str,
    ):
        self.id_variable = id_variable
        self.target_start_variable = target_start_variable
        self.target_end_variable = target_end_variable
        self.sort_by_variable_name = sort_by_variable_name
        self.new_first_variable_name = new_first_variable_name
        self.new_range_variable_name = new_range_variable_name
        self.new_difference_variable_name = new_difference_variable_name

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        if any(
            [
                x not in df.columns.values
                for x in [
                    self.id_variable,
                    self.target_start_variable,
                    self.target_end_variable,
                    self.sort_by_variable_name,
                ]
            ]
        ):
            raise ValueError(
                f"Expected valid variable names for `id_variable`, `target_start_variable`, `target_end_variable` and `sort_by_variable_name`, got `{self.id_variable}`, `{self.target_start_variable}`, `{self.target_end_variable}` and `{self.sort_by_variable_name}` instead"
            )

        if (
            df[
                [
                    self.id_variable,
                    self.target_start_variable,
                    self.target_end_variable,
                    self.sort_by_variable_name,
                ]
            ]
            .isnull()
            .values.any()
        ):
            raise ValueError(
                f"Expected no missing values for `id_variable`, `target_start_variable`, `target_end_variable` and `sort_by_variable_name`, got columns with nulls instead"
            )

        df = df.copy()

        # data need to be sorted
        df = df.sort_values([self.id_variable, self.sort_by_variable_name])

        # store range value (difference between end and start)
        df[self.new_range_variable_name] = (
            df[self.target_end_variable] - df[self.target_start_variable]
        )

        # store first value of target start variable
        df[self.new_first_variable_name] = df.groupby(self.id_variable)[
            self.target_start_variable
        ].transform("first")

        # add a temp column with the value of the previous line
        df["__end_tmp__"] = df.groupby(self.id_variable)[
            self.target_end_variable
        ].shift()

        # store the difference between current and previous value
        df[self.new_difference_variable_name] = (
            df[self.target_start_variable] - df["__end_tmp__"]
        )
        df[self.new_difference_variable_name] = df[
            self.new_difference_variable_name
        ].fillna(0)

        # remove the tmp column and the original target variables
        df = df.drop(
            columns=[
                self.target_start_variable,
                self.target_end_variable,
                "__end_tmp__",
            ]
        )

        # sort by index to return processed data in the original order
        df = df.sort_index()

        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        if any(
            [
                x not in dest.columns.values
                for x in [
                    self.id_variable,
                    self.new_first_variable_name,
                    self.new_range_variable_name,
                    self.new_difference_variable_name,
                ]
            ]
        ):
            raise ValueError(
                f"Expected valid variable names for `id_variable`, `new_first_variable_name`, `new_range_variable_name` and `new_difference_variable_name`, got `{self.id_variable}`, `{self.new_first_variable_name}`, `{self.new_range_variable_name}` and `{self.new_difference_variable_name}` instead"
            )

        if self.sort_by_variable_name not in source.columns.values:
            raise ValueError(
                f"Expected a valid `sort_by_variable_name`, got {self.sort_by_variable_name} instead"
            )

        if (
            dest[
                [
                    self.id_variable,
                    self.new_first_variable_name,
                    self.new_range_variable_name,
                    self.new_difference_variable_name,
                ]
            ]
            .isnull()
            .values.any()
        ):
            raise ValueError(
                f"Expected no missing values for `id_variable`, `new_first_variable_name`, `new_range_variable_name` and `new_difference_variable_name`, got columns with nulls instead"
            )

        if source[self.sort_by_variable_name].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `sort_by_variable_name` in source, got column with nulls instead"
            )

        df = dest.copy()

        # sort values in the same way as they were ordered in preprocess
        ordered_indices = source.sort_values(
            [self.id_variable, self.sort_by_variable_name]
        ).index
        df = df.loc[ordered_indices]

        # calculate for each row the sum of ranges of all previous records
        df["__range_tmp__"] = df.groupby(self.id_variable)[
            self.new_range_variable_name
        ].shift()
        df["__range_tmp__"] = df["__range_tmp__"].fillna(0)
        df["__totalizer_tmp__"] = df.groupby(self.id_variable)[
            "__range_tmp__"
        ].transform(pd.Series.cumsum) + df.groupby(self.id_variable)[
            self.new_difference_variable_name
        ].transform(
            pd.Series.cumsum
        )  # Fixed

        # calculate for each row the start value as the sum of the first value and the previously
        # calculated sum of ranges of all previous records (`__totalizer_tmp__`)
        df[self.target_start_variable] = (
            df[self.new_first_variable_name] + df["__totalizer_tmp__"]
        )  # Fix

        # calculate end values from start value and range value
        df[self.target_end_variable] = (
            df[self.target_start_variable] + df[self.new_range_variable_name]
        )

        # remove all temp columns and columns added at preprocessing
        df = df.drop(
            columns=[
                "__range_tmp__",
                "__totalizer_tmp__",
                self.new_difference_variable_name,
                self.new_range_variable_name,
                self.new_first_variable_name,
            ]
        )

        # sort by index to return data in the original order
        df = df.sort_index()
        return df
