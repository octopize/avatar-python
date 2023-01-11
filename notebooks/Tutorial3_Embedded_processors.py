# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
#   kernelspec:
#     display_name: 'Python 3.10.8 (''env'': venv)'
#     language: python
#     name: python3
# ---

# # Tutorial 3: Using embedded processors

# In this tutorial, we will learn how to to use some embedded processors to handle some characteristics of your dataset, for example, the presence of missing values, numeric variables with low cardinality, categorical variables with large cardinality or rare modalities.

# <img src="img/embedded.png" style="height:500px" />

# ## Connection

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

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import missingno as msno


# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

# ## Loading data
#
# To demonstrate the first embedded processor, we load the `adult` dataset which contains missing values. This dataset contains census data about the US population.

df = pd.read_csv("../fixtures/adult_with_missing.csv").head(1000)
dataset = client.pandas_integration.upload_dataframe(df)
print(df.shape)
df.head()

# ## Missing data
#
# Missing data is common in datasets and is a property that should be modelled.
#
# The Avatar solution can handle variables with missing data without requiring pre-processing. To do so, an additional variable defining whether a value is missing or not will be temporarily added to the data and the missing values will be temporarily imputed. These variables will be part of the anonymization process.
#
# In the presence of missing values, the last step in the avatarization will be to remove temporary variables and add back missing values.
#
# This transformation is embedded in the avatarization and only requires a user to set some imputation parameters.

print("Proportion of missing values per variable in originals")
df.isna().sum() / len(df)

imputation_parameters = ImputationParameters(k=5, method=ImputeMethod.knn)

# +
# %%time
# Create and run avatarization
job = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=5, dataset_id=dataset.id, imputation=imputation_parameters
        )
    )
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=1000)

# Download the avatars as a pandas dataframe
avatars = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)
# -

print("Proportion of missing values per variable in avatars")
avatars.isna().sum() / len(avatars)

# We observe that we the avatarization keeps the same proportion of missing values. But the location of the missing value cells in the data is not similar. This is because the missing value characteristics has also been anonymized.

msno.matrix(df)

msno.matrix(avatars)

# ### Handling missing data on large volumes

# Because there is an imputation step in the avatarization of data with missing values, it may yield long runtimes with some settings of the imputation. It is the case with the `ImputeMethod.knn` imputer demonstrated previously.
#
# To reduce the runtime caused by the imputation, it is possible to use an alternative imputation such as:
# - `ImputeMethod.fast_knn`, an appromixation of a knn imputer
# - `ImputeMethod.mean` that imputes using the mean of each variable (or mode if non-numeric)
# - `ImputeMethod.mode` that imputes using the mode of each variable
# - `ImputeMethod.median` that imputes using the median of each variable
#
# Another alternative is to use a fraction of the data for the impute step. This is controlled by the parameter `training_fraction` (the fraction of the dataset used to train the knn imputer).

# With this setting, only a 5th of the data will be used for imputation
imputation_parameters = ImputationParameters(
    k=5, method=ImputeMethod.knn, training_fraction=0.05
)

# +
# %%time
# Create and run avatarization
job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=5, dataset_id=dataset.id, imputation=imputation_parameters
        )
    )
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=1000)

print(job.status)
# -

# We observe faster runtime when using a fraction of the data for imputation.

# ## Numeric variables with low cardinality

# Some variables may be numeric but only contain several unique values. If their distributions show some peaks, these may not be preserved during avatarization.
#
# Let's take the Wisconcin Breast Cancer dataset (WBCD) as an example. This dataset contains categorical variables encoded as integers ranging between 0 and 10. The variable `Clump_Thickness` is one of them and exhibits a non-Gaussian distribution with peaks at different values

df = pd.read_csv("../fixtures/wbcd.csv")
df.shape

df.head()

df.dtypes

print("Number of distinct values:", df["Clump_Thickness"].nunique())
df["Clump_Thickness"].hist()

# ### Avatarization as numeric

# +
dataset = client.pandas_integration.upload_dataframe(df)

job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=20,
            dataset_id=dataset.id,
            imputation=ImputationParameters(method=ImputeMethod.mode),
        )
    )
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=1000)

# Download the avatars as a pandas dataframe
avatars = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)
# -

print("Number of distinct values in avatars:", avatars["Clump_Thickness"].nunique())
avatars["Clump_Thickness"].hist()

# An avatarization of this dataset without transformation of the low-cardinality numeric variables yields differences in the distribution.

# ### Avatarization as categorical

# +
job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=20,
            dataset_id=dataset.id,
            imputation=ImputationParameters(method=ImputeMethod.mode),
            to_categorical_threshold=20,
        )
    )
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=1000)

# Download the avatars as a pandas dataframe
avatars = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)
# -

print("Number of distinct values in avatars:", avatars["Clump_Thickness"].nunique())
avatars["Clump_Thickness"].hist()

# We observe that transforming some numeric variables to categorical can be beneficial. In our example, we preserve the proportion of each unique value where it may not be the case if we keep the variables as numeric.

# ## Categorical variables with large cardinality

# The anonymization of datasets containing categorical variables with large cardinality is not trivial and we recommend to exclude the variable from the avatarization before re-assigning it probabilistically.
#
# This necessary step is included in the avatarization job and can be managed via a set of parameters ExcludeCategoricalParameters.
#
# Metrics are computed after re-assignment of the excluded variables, so a variable that has been excluded is still anonymized as long as the privacy targets are reached.
#
# Note that we'll see in the next tutorial how other processors can be used as an alternative.
#
# First, let's load the `adult` dataset that now contains a `city` variable. This variable is categorical and contains over 80 modalities.

df = pd.read_csv("../fixtures/adult_with_cities.csv").head(1000)

df.head()

counts = df["city"].value_counts()
rare_values = set(counts[counts == 1].index)
print("Rare values for variable city are: ", rare_values)

counts

# ### Excluding variables and re-assigning them probabilistically

# +
# %%time
dataset = client.pandas_integration.upload_dataframe(df)

exclude_parameters = ExcludeCategoricalParameters(
    exclude_cardinality_threshold=30,
    exclude_replacement_strategy=ExcludeCategoricalMethod.coordinate_similarity,
    rare_occurence_threshold=1,
    rare_replacement_strategy=RareCategoricalMethod.most_similar,
)

job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=20,
            dataset_id=dataset.id,
            imputation=ImputationParameters(method=ImputeMethod.mode),
            exclude_categorical=exclude_parameters,
        )
    )
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=1000)

# Download the avatars as a pandas dataframe
avatars = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)
# -

avatars.head()

avatars["city"].value_counts()

# The exclude variable processor also ensures that rare modalities are not kept as they could be re-identifying. We can confirm this by looking at rare values from the original data still present in the avatars.

rare_values.intersection(set(avatars["city"].unique()))

# *In the next tutorial, we will show how to prepare the data prior to running an avatarization by using other processors on your local machine in order to handle and preserve other data characteristics.*
