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
# # Tutorial 1: A basic avatarization

# %% [markdown]
# In this tutorial, we will connect to a server to perform the avatarization of a dataset that does not require any pre-processing. We'll retrieve the anonymized dataset and the associated avatarization report.

# %%
import os
import secrets

import pandas as pd

from avatars.manager import Manager
from avatars.models import JobKind

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)

# %%
# Verify that we can connect to the API server
manager.auth_client.health.get_health()

# %% [markdown]
# ## Loading data

# %% [markdown]
# We recommend loading your file as a pandas dataframe. It enables you to check your data before avatarization and to pre-process it if required.
#
# In this tutorial, we use the simple and well-known `iris` dataset to demonstrate the main steps of an avatarization.

# %%
df = pd.read_csv("../fixtures/iris.csv")

# %%
df

# %%
# The runner is the object that will be used to upload data to the server and run the avatarization
runner = manager.create_runner(f"iris_k5_{secrets.token_hex(4)}")

# Then upload the data, you can either use a pandas dataframe or a file
runner.add_table("iris", df)

# %% [markdown]
# ## Creating and launching an avatarization job

# %%
runner.set_parameters("iris", k=5)

# %%
avatarization_job = (
    runner.run()
)  # by default we run all jobs : avatarization, privacy and signal metrics and report
# You can also choose to run only the avatarization job for example
# avatarization_job = runner.run(jobs_to_run=[JobKind.standard])

# %% [markdown]
# ## Retrieving the avatars

# %%
runner.shuffled("iris").head()

# %% [markdown]
# ## Retrieving the privacy metrics

# %%
runner.privacy_metrics("iris")[0]

# %% [markdown]
# ## Retrieving the signal metrics

# %%
runner.signal_metrics("iris")[0]

# %% [markdown]
# # Download the report

# %%
runner.download_report("my_report.pdf")

# %% [markdown]
# # How to print an error message
# There are multiple types of error and we encourage you to have a look at our [documentation](https://python.docs.octopize.io/latest/user_guide.html#understanding-errors) to understand them.
#
# The most common error is when server validation prevents a job from running.
#
# The following section show how to print an error message.

# %%
runner = manager.create_runner(f"iris_fail_{secrets.token_hex(4)}")
runner.add_table("iris", df)

runner.set_parameters("iris", k=500)  # k is too big (bigger than the dataset !)

runner.run(jobs_to_run=[JobKind.standard])

# %%
error_job = runner.get_job(JobKind.standard)
print(error_job.status)
print(error_job.exception)
