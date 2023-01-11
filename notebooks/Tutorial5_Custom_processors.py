# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Tutorial 5: Custom processors

# In this tutorial, we will learn how to define your own processor to be executed client-side.
#
# This is a useful feature allowing the integration of domain knowledge in the avatarization.

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

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

# ## Defining a custom processor

# We will use the `adult` dataset to demonstrate how a custom processor can be defined.

df = pd.read_csv("../fixtures/adult_with_cities.csv").head(1000)
dataset = client.pandas_integration.upload_dataframe(df)
print(df.shape)
df.head()

df["relationship"].value_counts()


# To be compatible with the avatarization pipeline, a processor must be defined following the structure:
#
# ```python
# class MyCustomProcessor:
#     def __init__(
#         self, <some_arguments>
#     ):
#         ...
#
#     def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
#         ...
#
#     def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
#         ...
# ```

# We can define a simple example processor that will group some modalities together in a preprocessing step and sample from the original modalities on the basis of the original frequencies in the postprocessing step.
#
# We can call this processor `GroupRelationshipProcessor`.

# We first define a constructor. To keep things simple, this processor will only take the name of the variable to transform.
#
# We then define a preprocess step. This step always takes a pandas dataframe as input and output a pandas dataframe


class GroupRelationshipProcessor:
    def __init__(self, variable_to_transform: str):
        self.variable_to_transform = variable_to_transform
        # Define modalities for new family and nofamily categories
        # Initialize frequencies to None
        self.family_frequencies = {"Husband": None, "Own-child": None, "Wife": None}
        self.nofamily_frequencies = {
            "Not-in-family": None,
            "Unmarried": None,
            "Other-relative": None,
        }

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        working = df.copy()

        # Store frequencies for family modalities
        family_data = working[
            working[self.variable_to_transform].isin(self.family_frequencies.keys())
        ]
        self.family_frequencies = (
            family_data[self.variable_to_transform].value_counts() / len(family_data)
        ).to_dict()

        # Store frequencies for nofamily modalities
        nofamily_data = working[
            working[self.variable_to_transform].isin(self.nofamily_frequencies.keys())
        ]
        self.nofamily_frequencies = (
            nofamily_data[self.variable_to_transform].value_counts()
            / len(nofamily_data)
        ).to_dict()

        # Replace original modality by new ones
        working[self.variable_to_transform] = [
            "family" if x in self.family_frequencies else "no_family"
            for x in working[self.variable_to_transform]
        ]
        return working

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        working = dest.copy()

        # Sample an old modality for each value
        working[self.variable_to_transform] = [
            np.random.choice(
                a=list(self.family_frequencies.keys()),
                p=list(self.family_frequencies.values()),
            )
            if x == "family"
            else np.random.choice(list(self.nofamily_frequencies.keys()))
            for x in working[self.variable_to_transform]
        ]
        return working


group_relationship_processor = GroupRelationshipProcessor(
    variable_to_transform="relationship"
)

preprocessed_df = group_relationship_processor.preprocess(df)

preprocessed_df["relationship"].value_counts()

postprocessed_df = group_relationship_processor.postprocess(df, preprocessed_df)

postprocessed_df.head()

# We now check that the postprocessed data contains approximatively each modality in the same proportion as in the original data

postprocessed_df["relationship"].value_counts()

df["relationship"].value_counts()

# ## Use custom processor  in the avatarization pipeline

# +
# %%time
dataset = client.pandas_integration.upload_dataframe(df)

result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5),
        ),
        processors=[group_relationship_processor],
        df=df,
    ),
    per_request_timeout=1000,
    timeout=1000,
)
# -

avatars = result.post_processed_avatars
avatars.head(5)

# +
privacy_metrics = result.privacy_metrics
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

utility_metrics = result.signal_metrics
print("\n*** Utility metrics ***")
for metric in utility_metrics:
    print(metric)
# -
