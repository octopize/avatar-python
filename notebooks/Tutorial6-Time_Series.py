# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
# ---

# # Tutorial 6: Time Series

# In this tutorial, we will perform the avatarization of data that contains time series. The approach presented here can be used to anonymize time series that contain a small number of data points.

# ## Connection

# +
import warnings

warnings.filterwarnings("ignore")

# +
import os

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import (
    AvatarizationJobCreate,
    AvatarizationParameters,
    ImputationParameters,
    ImputeMethod,
    ExcludeCategoricalParameters,
    ExcludeCategoricalMethod,
    RareCategoricalMethod,
)
from avatars.models import ReportCreate

from avatars.api import AvatarizationPipelineCreate
from avatars.processors.proportions import ProportionProcessor
from avatars.processors.group_modalities import GroupModalitiesProcessor
from avatars.processors.relative_difference import RelativeDifferenceProcessor
from avatars.processors.perturbation import PerturbationProcessor
from avatars.processors.expected_mean import ExpectedMeanProcessor

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

# ## Load some time series data

# We will use an example dataset that contains data on 2 sensors for 50 devices. For each device, 100 time points are available.

df = pd.read_csv("../fixtures/sensors.csv")

df

df.to_csv("../fixtures/sensors.csv", index=False)

sns.lineplot(
    df, x="t", y="sensor1", hue="id", palette=sns.color_palette(), legend=False
)

sns.lineplot(
    df, x="t", y="sensor2", hue="id", palette=sns.color_palette(), legend=False
)


# ## Prepare data for avatarization

# The avatarization takes as input tabular data where each row contains the data relative to an individual. In the present example, each row should ideally refer to a device.
#
# The number of time points to include in the avatarization can also have an impact and it is currently recommended to use a small number of data points (~ 5 to 10 points) to prevent cases where the data has more variables than individuals.
#
# To perform the transformation which consists in pivotting the table and sampling a given number of time points, we will use a processor.
#
# We can call this processor `SimpleTimeSeriesProcessor`.


class SimpleTimeSeriesProcessor:
    def __init__(
        self,
        n_points: int,
        id_variable: str,
        time_variable: str,
        values_variables: List[str],
    ):
        self.n_points = n_points
        self.id_variable = id_variable
        self.time_variable = time_variable
        self.values_variables = values_variables
        self.fixed_variables = None
        self.times = None

    def get_sampled_data_for_id(self, df, the_id, to_convert):
        df_individual = df[df[self.id_variable] == the_id]

        idx = np.round(np.linspace(0, len(df_individual) - 1, self.n_points)).astype(
            int
        )  # indices to sample
        df_sampled = df_individual.iloc[idx].reset_index(drop=True)  # sampling

        data = {self.id_variable: [the_id]}

        # Create one variable per pair {variable to convert - time step sampled}
        for c in to_convert:
            for i in df_sampled.index:
                data[c + "_" + str(i)] = [df_sampled.loc[i, c]]

        # For fixed variables, only create one variable and take the first value
        for c in self.fixed_variables:
            data[c] = [df_sampled.loc[0, c]]

        return data

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        dfs = []  # list of df, one per ID
        to_convert = self.values_variables.copy()
        to_convert.append(self.time_variable)
        self.fixed_variables = [
            c for c in df.columns if c not in to_convert and c != self.id_variable
        ]

        # For each ID, sample points evenly spaced
        for the_id in np.unique(df[self.id_variable]):
            data = self.get_sampled_data_for_id(df, the_id, to_convert)
            dfs.append(pd.DataFrame(data))

        working = pd.concat(dfs)
        working = working.reset_index(drop=True)

        # Save time columns (constant across all individuals) and remove them from preprocessed df
        time_columns = [self.time_variable + "_" + str(i) for i in range(self.n_points)]
        self.times = working[time_columns]
        working = working.drop(columns=time_columns)
        working = working.drop(columns=[self.id_variable])

        return working

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        working = dest.copy()

        # Add back the saved time information
        working = pd.concat([working, self.times], axis=1)

        # Transform time series variables
        data = {}
        for variable in self.values_variables:
            data[variable] = []
            for the_id in range(len(working)):
                for i in range(self.n_points):
                    data[variable].append(working.loc[the_id, variable + "_" + str(i)])

        # Transform time and ID variables
        data[self.time_variable] = []
        data[self.id_variable] = []
        for the_id in range(len(working)):
            for i in range(self.n_points):
                data[self.time_variable].append(
                    working.loc[the_id, self.time_variable + "_" + str(i)]
                )
                data[self.id_variable].append(the_id)

        # Transform fixed variables
        for c in self.fixed_variables:
            data[c] = []
            for the_id in range(len(working)):
                data[c].extend([working.loc[the_id, c] for _ in range(self.n_points)])

        postprocessed = pd.DataFrame(data)
        return postprocessed[df.columns]


# We can check that the behavior of the processor is as expected: after preprocessing, we should have *n_points* variables for each sensor and the static variables (i.e. the *model* variable)

timeseries_processor = SimpleTimeSeriesProcessor(
    n_points=10,
    id_variable="id",
    time_variable="t",
    values_variables=["sensor1", "sensor2"],
)

preprocessed_df = timeseries_processor.preprocess(df)

preprocessed_df.head()

# The post-processing step should reformat the data from the pre-processed form into the original one.

postprocessed_df = timeseries_processor.postprocess(df, preprocessed_df)
postprocessed_df.head()

# ## Avatarization

# The data is now in a classic tabular format and can be avatarized.

dataset = client.pandas_integration.upload_dataframe(preprocessed_df)
print(preprocessed_df.shape)

job = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=5, dataset_id=dataset.id)
    )
)

job = client.jobs.get_avatarization_job(id=job.id, timeout=1000)

print(job.status)

avatars_df = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)

avatars_df.head()

privacy_metrics = job.result.privacy_metrics
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

# ### Conversion of avatars back in original form

avatar_postprocessed_df = timeseries_processor.postprocess(df, avatars_df)

# ### Comparing original and avatarized time series
#
# Note that because the post-process step of our processor does not perform interpolation, we only plot the sampled original data and the avatars

# +
sampled_originals = timeseries_processor.postprocess(df, preprocessed_df)
fig, axs = plt.subplots(1, 2, figsize=(18, 8), sharey=True)

for ax, df, suptitle in zip(
    axs,
    [sampled_originals, avatar_postprocessed_df],
    ["Sampled original", "Sampled avatars"],
):
    sns.lineplot(
        ax=ax,
        data=df,
        x="t",
        y="sensor1",
        hue="id",
        palette=sns.color_palette(),
        legend=False,
    )
    ax.set_title(suptitle)

fig.suptitle("Comparison of sensor1 data", fontsize=20)

fig, axs = plt.subplots(1, 2, figsize=(18, 8), sharey=True)

for ax, df, suptitle in zip(
    axs,
    [sampled_originals, avatar_postprocessed_df],
    ["Sampled original", "Sampled avatars"],
):
    sns.lineplot(
        ax=ax,
        data=df,
        x="t",
        y="sensor2",
        hue="id",
        palette=sns.color_palette(),
        legend=False,
    )
    ax.set_title(suptitle)
fig.suptitle("Comparison of sensor2 data", fontsize=20)
