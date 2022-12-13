import warnings
from typing import List, Optional

import pandas as pd


class ExpectedMeanProcessor:
    def __init__(
        self,
        target_variables: List[str],
        *,
        groupby_variables: Optional[List[str]] = None,
        same_std: bool = False,
    ):
        """Processor to force values to have similar mean to original data.

        Means and standard deviations are computed for groups of variables and the
        processor ensures that the transformed data has similar mean and std than in
        the original data for each group.
        Care should be taken when using this processor as it only targets enhancement of unimodal
        utility. This may occur at the expense of multi-modal utility and privacy.

        Arguments
        ---------
            target_variables:
                variables to transform
            groupby_variables:
                variables to use to group values in different distributions
            same_std:
                Set to True to force the variables to transform to have the same
                standard deviation as the reference data. default: False.
        """
        # Variable added temporarily when no groupby is used. It is a column with only one modality
        # that can be used to perform a groupby in order to get the expected mean and std on all
        # records.
        self.nogroup_name = "___NOGROUPVAR___"
        self.nogroup_value = "__NOGROUPVAL__"
        if groupby_variables is None:
            self.groupby_variables = [self.nogroup_name]
            self.is_nogroup = True
        else:
            self.groupby_variables = groupby_variables
            self.is_nogroup = False
        self.target_variables = target_variables
        self.same_std = same_std

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute the reference mean and standard deviations.

        Arguments
        ---------
            df:
                reference dataframe

        Returns
        -------
            df:
                the unaltered reference dataframe.
        """
        working = df.copy()
        if self.is_nogroup:
            working[self.nogroup_name] = [
                self.nogroup_value for i in range(len(working))
            ]
        cols = self.groupby_variables + self.target_variables
        self.properties_df = _get_distribution_data(
            df=working[cols],
            target_variables=self.target_variables,
            groupby_variables=self.groupby_variables,
        )
        return working

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Force the data to have the reference mean.

        Arguments
        ---------
            source:
                not used
            dest:
                dataframe to transform

        Returns
        -------
            dest:
                a dataframe with the transformed target columns
        """
        original_cols = dest.columns
        if self.is_nogroup:
            # if no groupby, create a one-modality temporary variable
            dest[self.nogroup_name] = [self.nogroup_value] * len(dest)
        cols = self.groupby_variables + self.target_variables
        current_properties_df = _get_distribution_data(
            df=dest[cols],
            target_variables=self.target_variables,
            groupby_variables=self.groupby_variables,
        )
        current_properties_df = current_properties_df.rename(
            columns={
                f"{col}mean": f"{col}mean_current" for col in self.target_variables
            }
        )
        current_properties_df = current_properties_df.rename(
            columns={f"{col}std": f"{col}std_current" for col in self.target_variables}
        )

        dest = dest.merge(
            current_properties_df,
            left_on=self.groupby_variables,
            right_on=self.groupby_variables,
        )
        dest = dest.merge(
            self.properties_df,
            left_on=self.groupby_variables,
            right_on=self.groupby_variables,
        )

        for col in self.target_variables:
            same_std_tmp = self.same_std
            if self.same_std and 0 in current_properties_df[f"{col}std_current"].values:
                warnings.warn(
                    f"""target variable {col} has a std of 0. The same standard deviation
                            cannot be guaranteed for this variable.
                    """
                )
                same_std_tmp = False
            if same_std_tmp:
                dest[col] = dest[f"{col}mean"] + (
                    dest[col] - dest[f"{col}mean_current"]
                ) * (dest[f"{col}std"] / dest[f"{col}std_current"])
            else:
                dest[col] = dest[f"{col}mean"] + (
                    dest[col] - dest[f"{col}mean_current"]
                )

        dest = dest[original_cols]

        return dest


def _get_distribution_data(
    df: pd.DataFrame,
    target_variables: List[str],
    groupby_variables: List[str],
) -> pd.DataFrame:
    """Get mean and standard deviation for given variables and groupby.

    Arguments
    ---------
        df:
            data on which to compute statistics
        target_variables:
            list of columns on which to compute statistics
        groupby_variables:
            list of columns to aggregate on

    Returns
    -------
        stats_df:
            statistics dataframe.
    """
    # Define transformations to perform
    aggregation_dict = {}
    for col in target_variables:
        aggregation_dict[col] = ["mean", "std"]

    # Perform transformations
    stats_df = (
        df.groupby(groupby_variables, dropna=False).agg(aggregation_dict).reset_index()
    )

    # Flatten and set new aggregate variable names
    stats_df.columns = ["".join(a) for a in stats_df.columns.to_flat_index()]

    return stats_df
