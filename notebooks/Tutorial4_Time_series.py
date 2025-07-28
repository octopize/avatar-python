# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.1
# ---

# %% [markdown]
# # Tutorial 4: Time Series

# %% [markdown]
# In this tutorial, we will perform the avatarization of data containing time series variables. This is a specific case of a multitable avatarization

# %% [markdown]
# ## Connection

# %%
import os
import secrets

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from avatar_yaml.models.parameters import ProjectionType
from avatar_yaml.models.schema import LinkMethod

from avatars.manager import Manager

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)
# Verify that we can connect to the API server
manager.get_health()

# %% [markdown]
# ## Loading data

# %% [markdown]
# In this tutorial, we use data that contains readings from 3 sensors for 200 individuals. The data is divided into 3 datasets as follows:
# - `sensors_vanilla.csv`: demographic data on individuals, each line refers to one individual and contains 15 variables (similar to adult data seen in previous tutorials)
# - `sensors_timeseries1.csv`: time series data for `sensor1` and `sensor2`. The data contains an identifier variable (`id`) and a time variable (`t`). There are several lines for each individual.
# - `sensors_timeseries2.csv`: time series data for `sensor3`. Note that this time series data can have different timestamps than the other time series and a different number of measurements.

# %%
vanilla_df = pd.read_csv("../fixtures/sensors_vanilla.csv")
ts1_df = pd.read_csv("../fixtures/sensors_timeseries1.csv")
ts2_df = pd.read_csv("../fixtures/sensors_timeseries2.csv")

# %%
vanilla_df.head()

# %% [markdown]
# **Note that the vanilla data contains a column `id` required to link time series data point with each individual.**

# %%
ts1_df

# %%
ts2_df


# %% [markdown]
# ## Overview of data

# %% [markdown]
# We provide below a basic visualization function to better understand how the time series data look like.


# %%
def plot_series(
    df: pd.DataFrame,
    variable_to_plot: str,
    id_variable: str,
    time_variable: str,
    proportion_to_plot: float = 1.0,
    n_series_to_plot: int | None = None,
    figsize: tuple[int, int] = (14, 8),
) -> matplotlib.figure.Figure:
    """Plot given series."""
    if n_series_to_plot is None:
        n_series_to_plot = df[id_variable].unique().shape[0]

    df_tmp = df.copy()
    df_tmp = df_tmp.sort_values(by=[id_variable, time_variable]).reset_index(drop=True)

    cmap = plt.get_cmap("gist_rainbow")

    fig, ax = plt.subplots(figsize=figsize)
    for id_nb, id_name in enumerate(set(df_tmp[id_variable])):
        if id_nb > n_series_to_plot:
            break
        selected_records = df_tmp[df_tmp[id_variable] == id_name]
        n_points = int(proportion_to_plot * len(selected_records))
        selected_indices = np.linspace(0, len(selected_records) - 1, num=n_points)

        x = selected_records[time_variable].iloc[selected_indices]
        y = selected_records[variable_to_plot].iloc[selected_indices]
        ax.plot(x, y, color=cmap(id_nb / n_series_to_plot))
    ax.set_title(f"Series for variable {variable_to_plot}")
    return fig


# %% [markdown]
# and we use it to plot sensor data for some individuals

# %% [markdown]
# ### `sensor1` data

# %%
plot = plot_series(
    df := ts1_df,
    variable_to_plot="sensor1",
    id_variable="id",
    time_variable="t",
    proportion_to_plot=1.0,
    n_series_to_plot=None,
    figsize=(14, 8),
)
plot.show()

# %% [markdown]
# ###  `sensor2` data

# %%
plot = plot_series(
    df := ts1_df,
    variable_to_plot="sensor2",
    id_variable="id",
    time_variable="t",
    proportion_to_plot=1.0,
    n_series_to_plot=None,
    figsize=(14, 8),
)
plot.show()

# %% [markdown]
# ### `sensor3` data

# %%
plot = plot_series(
    df := ts2_df,
    variable_to_plot="sensor3",
    id_variable="id",
    time_variable="t",
    proportion_to_plot=1.0,
    n_series_to_plot=None,
    figsize=(14, 8),
)
plot.show()

# %% [markdown]
# Now that we know what data we are maniplating, we can anonymize it.

# %% [markdown]
# ## Avatars of time series data

# %% [markdown]
# Avatarizing time_series data is a specific case of multitable avatarization. Please see Tutorial3.
# You will need to use a specific LinkMethod : `TIME_SERIES` and to specify the time scale variable `t`

# %% [markdown]
# ### Upload data and save datasets

# %%
# First initialize the runner
runner = manager.create_runner(f"tutorial_time_series_{secrets.token_hex(4)}")

# Then upload the data
runner.add_table("vanilla", vanilla_df, individual_level=True, primary_key="id")
runner.add_table(
    "sensor1", ts1_df, primary_key="primary_key", foreign_keys=["id"], time_series_time="t"
)
runner.add_table(
    "sensor2", ts2_df, primary_key="primary_key", foreign_keys=["id"], time_series_time="t"
)

# %% [markdown]
# ### add links between tables

# %%
runner.add_link(
    parent_table_name="vanilla",
    parent_field="id",
    child_table_name="sensor1",
    child_field="id",
    method=LinkMethod.TIME_SERIES,
)

runner.add_link(
    parent_table_name="vanilla",
    parent_field="id",
    child_table_name="sensor2",
    child_field="id",
    method=LinkMethod.TIME_SERIES,
)

# %% [markdown]
# ### Create job and retrieve results
#
# This is done in a similar way than for the anonymization of classic tabular data.
#
# The attributes that are specific to time_series anonymization are:
# - `time_series_projection_type`: The projection parameters defines how the data will be transformed (aka projected) so that avatars can be generated.
# - `time_series_nf`:  This is the number of components used to represent each time series variable in the projection.
# - `time_series_nb_points` :
# - `time_series_method`:

# %%
runner.set_parameters("vanilla", k=5)
runner.set_parameters(
    "sensor1", time_series_projection_type=ProjectionType.FLATTEN, time_series_nf=10
)
runner.set_parameters(
    "sensor2", time_series_projection_type=ProjectionType.FLATTEN, time_series_nf=10
)

# %%
runner.run()
results = runner.get_all_results()

# %% [markdown]
# ### Retrieve avatars
#
# Once generated, the avatar dataset are stored on the server and can be retrieved using their dataset names.

# %% [markdown]
# ### Checking your avatars: vanilla data

# %%
avatars_vanilla = runner.shuffled("vanilla")
avatars_vanilla.head()

# %% [markdown]
# ### Checking your avatars: `sensor1` and `sensor2`

# %%
avatars_ts1_df = runner.shuffled("sensor1")
avatars_ts1_df.head()

# %%
plot = plot_series(
    df := avatars_ts1_df,
    variable_to_plot="sensor1",
    id_variable="id",
    time_variable="t",
    proportion_to_plot=1.0,
    n_series_to_plot=None,
    figsize=(14, 8),
)
plot.show()

# %%
plot = plot_series(
    df := avatars_ts1_df,
    variable_to_plot="sensor2",
    id_variable="id",
    time_variable="t",
    proportion_to_plot=1.0,
    n_series_to_plot=None,
    figsize=(14, 8),
)
plot.show()

# %% [markdown]
# ### Checking your avatars: `sensor3`

# %%
avatars_ts2_df = runner.shuffled("sensor2")
avatars_ts2_df.head()

# %%
plot = plot_series(
    df := avatars_ts2_df,
    variable_to_plot="sensor3",
    id_variable="id",
    time_variable="t",
    proportion_to_plot=1.0,
    n_series_to_plot=None,
    figsize=(14, 8),
)
plot.show()

# %% [markdown]
# ## Privacy metrics for time series

# %% [markdown]
# As for any data, privacy metrics need to be computed on the output time series data to confirm that it is anonymous. We first retrieve the data required by the privacy metrics, that is the original datasets and their sensitive unshuffled counterparts. The unshuffled datasets are only used for computing the privacy metrics

# %% [markdown]
# Metric results are calculated for each dataset and are stored in `privacy_job.result`

# %%
for metric_details in runner.privacy_metrics("vanilla")[0].items():
    print(metric_details)

# %%
for metric_details in runner.privacy_metrics("sensor1")[0].items():
    print(metric_details)

# %%
for metric_details in runner.privacy_metrics("sensor2")[0].items():
    print(metric_details)

# %% [markdown]
# ## Signal metrics for time series data

# %%
for metric_details in runner.signal_metrics("vanilla")[0].items():
    print(metric_details)

# %%
for metric_details in runner.signal_metrics("sensor1")[0].items():
    print(metric_details)

# %%
for metric_details in runner.signal_metrics("sensor2")[0].items():
    print(metric_details)

# %% [markdown]
# ## Download report

# %%
runner.download_report("time_series_report.pdf")
