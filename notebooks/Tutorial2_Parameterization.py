# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.2
# ---

# # Tutorial 2: Parameterizing an avatarization

# In this tutorial, we will learn how to set key parameters of the avatarization and how they impact privacy and utility.

# ## Connection

# +
import os

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")
# -

# Run the following cell if your environment does not have all the listed packages already installed.

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters
from avatars.models import ReportCreate

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io
import numpy as np

import seaborn as sns
import matplotlib.pyplot as plt

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

# ## Loading data
#
# This tutorial uses the `iris` dataset, allowing us to run several avatarization without delays.

df = pd.read_csv("../fixtures/iris.csv")
dataset = client.pandas_integration.upload_dataframe(df)

df.head()

# ## Varying k
#
# The parameter *k* can be used to control the tradeoff between privacy and utility. To increase privacy, we recommend increasing the value of k. Because k is the parameter that also impacts the most the utility, it is recommended to alter it gradually.
#
# We demonstrate here the effect of varying *k*.
#

# +
# Set k
k = 2

# Create and run avatarization
job_small_k = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=k, dataset_id=dataset.id)
    )
)
job_small_k = client.jobs.get_avatarization_job(id=job_small_k.id, timeout=100)

# Retrieve selected metric
hidden_rate = job_small_k.result.privacy_metrics.hidden_rate
local_cloaking = job_small_k.result.privacy_metrics.local_cloaking
hellinger_distance = job_small_k.result.signal_metrics.hellinger_mean

print(f"With k={k}, the hidden_rate (privacy) is : {hidden_rate}")
print(f"With k={k}, the local_cloaking (privacy) is : {local_cloaking}")
print(f"With k={k}, the hellinger_distance (utility) is : {hellinger_distance}")

# +
# Set k
k = 30

# Create and run avatarization
job_large_k = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=k, dataset_id=dataset.id)
    )
)
job_large_k = client.jobs.get_avatarization_job(id=job_large_k.id, timeout=100)

# Retrieve selected metric
hidden_rate = job_large_k.result.privacy_metrics.hidden_rate
local_cloaking = job_large_k.result.privacy_metrics.local_cloaking
hellinger_distance = job_large_k.result.signal_metrics.hellinger_mean

print(f"With k={k}, the hidden_rate (privacy) is : {hidden_rate}")
print(f"With k={k}, the local_cloaking (privacy) is : {local_cloaking}")
print(f"With k={k}, the hellinger_distance (utility) is : {hellinger_distance}")
# -

# We observe that we are able to increase the level of privacy by simply increasing *k*. But this is at the expense of the utility.

# ## Visualization of originals and avatars

# By looking at original and avatars in the projected space, we can understand the area covered by avatars and if it covers the same space as the original data.

projections = client.metrics.get_job_projections(job_id=job_small_k.id)
projections_records = np.array(projections.records)[
    :, 0:2
]  # First 2 dimensions of projected records
projections_avatars = np.array(projections.avatars)[
    :, 0:2
]  # First 2 dimensions of projected records

projections

# +
fig, ax = plt.subplots(1, 1)
sns.scatterplot(
    ax=ax,
    x=projections_records[:, 0],
    y=projections_records[:, 1],
    alpha=0.6,
    color="dimgrey",
    label="Original",
)

sns.scatterplot(
    ax=ax,
    x=projections_avatars[:, 0],
    y=projections_avatars[:, 1],
    alpha=0.6,
    color="#3BD6B0",
    label="Avatars",
)

ax.set_title("Projections of original and avatars produced with small k")

# +
projections = client.metrics.get_job_projections(job_id=job_large_k.id)
projections_records = np.array(projections.records)[
    :, 0:2
]  # First 2 dimensions of projected records
projections_avatars = np.array(projections.avatars)[
    :, 0:2
]  # First 2 dimensions of projected records

fig, ax = plt.subplots(1, 1)
sns.scatterplot(
    ax=ax,
    x=projections_records[:, 0],
    y=projections_records[:, 1],
    alpha=0.6,
    color="dimgrey",
    label="Original",
)

sns.scatterplot(
    ax=ax,
    x=projections_avatars[:, 0],
    y=projections_avatars[:, 1],
    alpha=0.6,
    color="#3BD6B0",
    label="Avatars",
)

ax.set_title("Projections of original and avatars produced with large k")
# -

# We observe that the area covered by avatars generated with a low *k* is much closer to the area covered by original data points. We can also see that with a low *k*, some avatars are close to original points that are isolated. This may pose a risk of re-identification. This explains the drop in privacy level when reducing *k*.
#
# Avatars produced with a large *k* are significantly further away from isolated originals and so ensure their privacy. However care should be taken in setting *k*  with values that are not too high to prevent a drop in utility level. The drop in utility level is represented by the area covered by avatars being much smaller than the ones of originals.

# ## Other parameters

# ### Column weights
#
# Column weights represent the importance of each variable during the projection process. The higher the value for one variable, the more the individuals will be separated regarding this variable.
#
# By default, all variables are given equal weight of 1, but custom weights can be defined to bias the projection towards some specific variables.

column_weights = {"variety": 3}

# ### Number of components
#
# The number of components represents the number of dimensions to consider for the KNN algorithm. With a low value, computation will mostly be based on well-represented variables in the projection.
#
# By default, `ncp` is set to 5, meaning that the 5 dimensions in the projected space that represent the most the variance on the data are used when computing neighbors.

ncp = 5

# ### Seed
#
# A seed is a helpful feature to enable reproducible experiments. However, a seed should not be set in production to ensure that avatars are unique and that the originals cannot be retro-engineered.
#
# By default, `seed` is set to `None`.

seed = 123

# The avatarization can now be run with different parameters

# +
parameters = AvatarizationParameters(
    k=k, dataset_id=dataset.id, column_weights=column_weights, ncp=ncp, seed=seed
)

job = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(parameters=parameters)
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=100)
# -

# We will now observe the impact of the parameters on the projections. We recommend executing this last part of the tutorial several times with different settings.

# +
projections = client.metrics.get_job_projections(job_id=job.id)
projections_records = np.array(projections.records)[
    :, 0:2
]  # First 2 dimensions of projected records
projections_avatars = np.array(projections.avatars)[
    :, 0:2
]  # First 2 dimensions of projected records

fig, ax = plt.subplots(1, 1)
sns.scatterplot(
    ax=ax,
    x=projections_records[:, 0],
    y=projections_records[:, 1],
    alpha=0.6,
    color="dimgrey",
    label="Original",
)

sns.scatterplot(
    ax=ax,
    x=projections_avatars[:, 0],
    y=projections_avatars[:, 1],
    alpha=0.6,
    color="#3BD6B0",
    label="Avatars",
)

ax.set_title("Projections of original and avatars produced with custom settings")
# -

# *In the next tutorial, we will show how to use some embedded processors to handle some characteristics of your dataset, for example, the presence of missing values, numeric variables with low cardinality, categorical variables with large cardinality or rare modalities.*
#
