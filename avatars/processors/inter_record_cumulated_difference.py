import pandas as pd


class InterRecordCumulatedDifferenceProcessor:
    """Processor to express the value of a variable as the difference from the previous value.

    This processor can be used only on data where there are several records for each individual.
    By this transformation, a variable whose value is cumulative will be expressed as:
    - a variable containing its first value.
    - a variable containing the difference from the previous record

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
        keep_record_order:
            If set to `True`, the postprocess will decode values respecting the record order given
            by `id_variable` and `sort_by_variable` from the source dataframe. This can only be set
            to `True` if the indices are the same between the source and dest dataframes passed as
            arguments to `postprocess`.
    Examples
    --------
    >>> df = pd.DataFrame({
    ...    "id": [1, 2, 1, 1, 2, 2],
    ...    "value": [1025, 20042, 1000, 1130, 20000, 20040],
    ... })
    >>> processor = InterRecordCumulatedDifferenceProcessor(
    ...    id_variable='id',
    ...    target_variable='value',
    ...    new_first_variable_name='first_value',
    ...    new_difference_variable_name='value_difference',
    ...    keep_record_order=True
    ...    )
    >>> processor.preprocess(df)
       id  first_value  value_difference
    0   1         1000              25.0
    1   2        20000               2.0
    2   1         1000               0.0
    3   1         1000             105.0
    4   2        20000               0.0
    5   2        20000              40.0

    The postprocess allows you to transform some preprocessed data back into its original format

    >>> preprocessed_df = pd.DataFrame({
    ...    "id": [1, 2, 1, 1, 2, 2],
    ...    "first_value": [1000, 20000, 1000, 1000, 20000, 20000],
    ...    "value_difference": [25, 2, 0, 105, 0, 40],
    ... })
    >>> processor.postprocess(df, preprocessed_df)
       id  value
    0   1   1025
    1   2  20042
    2   1   1000
    3   1   1130
    4   2  20000
    5   2  20040

    The postprocess can also be used on data where the number of records per individual is
    different than the original one. In such cases, the processor should be instantiated with the
    `keep_record_order` argument set to its default value `False`.
    In the example below, there is an extra record with the id 2.

    >>> processor = InterRecordCumulatedDifferenceProcessor(
    ...    id_variable='id',
    ...    target_variable='value',
    ...    new_first_variable_name='first_value',
    ...    new_difference_variable_name='value_difference',
    ...    keep_record_order=False
    ... )
    >>> preprocessed_df = pd.DataFrame({
    ...    "id": [1, 2, 1, 1, 2, 2, 2],
    ...    "first_value": [1000, 20000, 1000, 1000, 20000, 20000, 20000],
    ...    "value_difference": [25, 2, 0, 105, 0, 40, 8],
    ... })
    >>> processor.postprocess(df, preprocessed_df)
       id  value
    0   1   1025
    1   2  20002
    2   1   1025
    3   1   1130
    4   2  20002
    5   2  20042
    6   2  20050
    """

    def __init__(
        self,
        *,
        id_variable: str,
        target_variable: str,
        new_first_variable_name: str,
        new_difference_variable_name: str,
        keep_record_order: bool = False,
    ):
        self.id_variable = id_variable
        self.target_variable = target_variable
        self.new_first_variable_name = new_first_variable_name
        self.new_difference_variable_name = new_difference_variable_name
        self.keep_record_order = keep_record_order

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

        df = df.copy()

        # data need to be sorted by target value asc
        df = df.sort_values([self.id_variable, self.target_variable])

        # store first value of target variable
        df[self.new_first_variable_name] = df.groupby(self.id_variable)[
            self.target_variable
        ].transform("first")

        # add a temp column with the value of the previous line
        df["tmp"] = df.groupby(self.id_variable)[self.target_variable].shift()

        # store the difference between current and previous value
        df[self.new_difference_variable_name] = df[self.target_variable] - df["tmp"]
        df[self.new_difference_variable_name] = df[
            self.new_difference_variable_name
        ].fillna(0)

        # remove the tmp column and the original target variable
        df = df.drop(columns=[self.target_variable, "tmp"])

        # sort by index to return processed data in the original order
        df = df.sort_index()

        return df

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
                [self.id_variable, self.target_variable]
            ).index
            df = df.loc[ordered_indices]

        # calculate target value as first value + cumulated sum of the differences
        df[self.target_variable] = df[self.new_first_variable_name] + df.groupby(
            self.id_variable
        )[self.new_difference_variable_name].transform(pd.Series.cumsum)

        df = df.drop(
            columns=[self.new_first_variable_name, self.new_difference_variable_name]
        )

        # sort by index to return data in the original order
        df = df.sort_index()

        return df
