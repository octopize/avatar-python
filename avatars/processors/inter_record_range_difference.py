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

    This processor can be used to express a quantity that varies at each event (variation defined
    by a start and an end) but also that varies across successive events.

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
        keep_record_order:
            If set to `True`, the postprocess will decode values respecting the record order given
            by `id_variable` and `sort_by_variable` from the source dataframe. This can only be set
            to `True` if the indices are the same between the source and dest dataframes passed as
            arguments to `postprocess`.
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
    ...     sort_by_variable="start",
    ...     new_first_variable="first_value",
    ...     new_range_variable='range_value',
    ...     new_difference_variable="value_difference",
    ...     keep_record_order=True
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

    The postprocess can also be used on data where the number of records per individual is
    different than the original one. In such cases, the processor should be instantiated with the
    `keep_record_order` argument set to its default value `False`.
    In the example below, there is an extra record with the id 2.

    >>> processor = InterRecordRangeDifferenceProcessor(
    ...     id_variable="id",
    ...     target_start_variable='start',
    ...     target_end_variable='end',
    ...     sort_by_variable="start",
    ...     new_first_variable="first_value",
    ...     new_range_variable='range_value',
    ...     new_difference_variable="value_difference",
    ...     keep_record_order=False
    ... )
    >>> preprocessed_df = pd.DataFrame(
    ...     {
    ...         "id": [1, 2, 1, 1, 2, 2, 2],
    ...         "range_value": [1, 4, 1, 3, 2, 1, 2],
    ...         "first_value": [6, 10, 6, 6, 10, 10, 10],
    ...         "value_difference": [0, 2, 0, 4, 0, 5, 1],
    ...     }
    ... )
    >>> processor.postprocess(df, preprocessed_df)
       id  start   end
    0   1    6.0   7.0
    1   2   12.0  16.0
    2   1    7.0   8.0
    3   1   12.0  15.0
    4   2   16.0  18.0
    5   2   23.0  24.0
    6   2   25.0  27.0
    """

    def __init__(
        self,
        *,
        id_variable: str,
        target_start_variable: str,
        target_end_variable: str,
        sort_by_variable: str,
        new_first_variable: str,
        new_range_variable: str,
        new_difference_variable: str,
        keep_record_order: bool = False,
    ):
        self.id_variable = id_variable
        self.target_start_variable = target_start_variable
        self.target_end_variable = target_end_variable
        self.sort_by_variable = sort_by_variable
        self.new_first_variable = new_first_variable
        self.new_range_variable = new_range_variable
        self.new_difference_variable = new_difference_variable
        self.keep_record_order = keep_record_order

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        variables_to_check = [
            self.id_variable,
            self.target_start_variable,
            self.target_end_variable,
            self.sort_by_variable,
        ]
        if len(set(variables_to_check).difference(df.columns.values)) > 0:
            raise ValueError(
                "Expected valid variable names for `id_variable`, `target_start_variable`, "
                "`target_end_variable` and `sort_by_variable`, got "
                f"'{self.id_variable}', '{self.target_start_variable}', "
                f"'{self.target_end_variable}' and '{self.sort_by_variable}' instead"
            )

        if df[variables_to_check].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `id_variable`, `target_start_variable`, "
                "`target_end_variable` and `sort_by_variable`, got columns with nulls instead"
            )

        df = df.copy()

        # data needs to be sorted
        df = df.sort_values([self.id_variable, self.sort_by_variable])

        # store range value (difference between end and start)
        df[self.new_range_variable] = (
            df[self.target_end_variable] - df[self.target_start_variable]
        )

        # store first value of target start variable
        df[self.new_first_variable] = df.groupby(self.id_variable)[
            self.target_start_variable
        ].transform("first")

        # add a temp column with the value of the previous line
        df["__end_tmp__"] = df.groupby(self.id_variable)[
            self.target_end_variable
        ].shift()

        # store the difference between current and previous value
        df[self.new_difference_variable] = (
            df[self.target_start_variable] - df["__end_tmp__"]
        )
        df[self.new_difference_variable] = df[self.new_difference_variable].fillna(0)

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
        variables_to_check = [
            self.id_variable,
            self.new_first_variable,
            self.new_range_variable,
            self.new_difference_variable,
        ]
        if len(set(variables_to_check).difference(dest.columns.values)) > 0:
            raise ValueError(
                "Expected valid variable names for `id_variable`, `new_first_variable`, "
                "`new_range_variable` and `new_difference_variable`, "
                f"got '{self.id_variable}', '{self.new_first_variable}', "
                f"'{self.new_range_variable}' and '{self.new_difference_variable}' instead"
            )

        if self.sort_by_variable not in source.columns.values:
            raise ValueError(
                f"Expected a valid `sort_by_variable`, got '{self.sort_by_variable}' instead"
            )

        if dest[variables_to_check].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `id_variable`, "
                "`new_first_variable`, `new_range_variable` and `new_difference_variable`, "
                "got columns with nulls instead"
            )

        if source[self.sort_by_variable].isnull().values.any():
            raise ValueError(
                "Expected no missing values for `sort_by_variable` in source, "
                "got column with nulls instead"
            )

        if (
            self.keep_record_order
            and len(set(source.index).symmetric_difference(dest.index)) > 0
        ):
            raise ValueError(
                "Expected `keep_record_order` to be `True` only if source and dest "
                "have same indices, got source and dest with different indices"
            )

        df = dest.copy()

        # sort values in the same way as they were ordered in preprocess
        if self.keep_record_order:
            ordered_indices = source.sort_values(
                [self.id_variable, self.sort_by_variable]
            ).index
            df = df.loc[ordered_indices]

        # calculate for each row the sum of ranges of all previous records
        df["__range_tmp__"] = df.groupby(self.id_variable)[
            self.new_range_variable
        ].shift()
        df["__range_tmp__"] = df["__range_tmp__"].fillna(0)
        df["__totalizer_tmp__"] = df.groupby(self.id_variable)[
            "__range_tmp__"
        ].transform(pd.Series.cumsum) + df.groupby(self.id_variable)[
            self.new_difference_variable
        ].transform(
            pd.Series.cumsum
        )

        # calculate for each row the start value as the sum of the first value and the previously
        # calculated sum of ranges of all previous records (`__totalizer_tmp__`)
        df[self.target_start_variable] = (
            df[self.new_first_variable] + df["__totalizer_tmp__"]
        )

        # calculate end values from start value and range value
        df[self.target_end_variable] = (
            df[self.target_start_variable] + df[self.new_range_variable]
        )

        # remove all temp columns and columns added at preprocessing
        df = df.drop(
            columns=[
                "__range_tmp__",
                "__totalizer_tmp__",
                self.new_difference_variable,
                self.new_range_variable,
                self.new_first_variable,
            ]
        )

        # sort by index to return data in the original order
        df = df.sort_index()
        return df
