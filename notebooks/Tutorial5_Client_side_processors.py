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
# # Tutorial 5: Client-side processors

# %% [markdown]
# In this tutorial, we will learn how to prepare the data prior to running an avatarization by using processors on your local machine.
#
# This step is necessary in some cases to handle and preserve data characteristics that are not natively handled by the avatarization or its embedded processors.
#
# We'll also show how custom client-side processors can be defined to integrate domain knowledge into an avatarization.

# %% [markdown]
# ## Principles

# %% [markdown]
# ![pipeline](img/pipeline.png)

# %% [markdown]
# ## Connection

# %%
from avatars.manager import Manager
from avatars.models import JobKind
from avatars.runner import Results
import numpy as np

import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import os

url = os.environ.get("AVATAR_BASE_API_URL","https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)
# Verify that we can connect to the API server
manager.get_health()

# %% [markdown]
# ## A helper processor to reduce the number of modalities

# %% [markdown]
# We have seen in the previous tutorial one approach to handle categorical variables with large cardinality. We propose here an alternative way of doing this using a client-side processor.
#
# This processor will group modalities together to ensure the target variable has a requested number of modalities. The least represented modalities will be brought together under a `other` modality. Note that this transformation is irreversible (the original value cannot be infered from `other`).
#
# Because this is an irreversible operation, this transformation of the data should be done outside the pipeline. The transformed data will be used as a basis for comparison when computing utility and privacy metrics.

# %%
df = (
    pd.read_csv("../fixtures/adult_with_cities.csv")
    .head(1000)
    .drop(["native-country"], axis=1)
)
df.head()

# %% [markdown]
# After loading the data, we decide we wish to reduce the number of modalities for the variable `city` which contains originally over 80 distinct values.

# %%
df["city"].value_counts()

# %%
from avatars.processors import GroupModalitiesProcessor
group_modalities_processor = GroupModalitiesProcessor(
    min_unique=10,  # number of modalities for a variable to be considered for grouping
    global_threshold=25,  # if considered for grouping, number of individuals in modality to preserve it
    new_category="other",
)

# %%
df_preprocessed = group_modalities_processor.preprocess(df)

# %% [markdown]
# Once the group modality processor has been applied, we can confirm that the number of modalities for the `city` variables has been reduced

# %%
df_preprocessed["city"].value_counts()

# %%
runner = manager.create_runner(set_name="tutorial5")
runner.add_table(
    "adult",
    df_preprocessed,
)
runner.set_parameters("adult",k=5)
runner.run(jobs_to_run=[JobKind.standard])
runner.get_all_results()

# %%
avatars = runner.shuffled("adult")
avatars.head(3)

# %%
avatars["city"].value_counts()

# %% [markdown]
# We observe that the avatars produced have a reduced number of cities and an extra `other` modality for the `city` variable. Note that the use of a client-side processor made the transformation of the data straightforward.
