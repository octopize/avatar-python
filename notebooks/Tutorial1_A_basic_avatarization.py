# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.2
# ---

# %% [markdown]
# # Tutorial 1: A basic avatarization

# %% [markdown]
# In this tutorial, we will connect to a server to perform the avatarization of a dataset that does not require any pre-processing. We'll retrieve the anonymized dataset and the associated avatarization report.

# %%
import os

import pandas as pd
from avatar_yaml.models.parameters import ReportType

from avatars.manager import Manager
from avatars.models import JobKind

username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %%
manager = Manager()  # or manager = Manager(base_url=https://your-server.com)
# Authenticate with the server
manager.authenticate(username, password, should_verify_compatibility=False)

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
runner = manager.create_runner("iris_k5")

# Then upload the data, you can either use a pandas dataframe or a file
runner.add_table("iris", df)

# %% [markdown]
# ## Creating and launching an avatarization job

# %%
runner.advise_parameters("iris")
runner.update_parameters("iris", k=5)  # if you want to change a specific parameter

# %%
runner.table_summary("iris")

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

# %% [markdown]
# We provide 2 kinds of report, a technical report and a PIA (Privacy Impact Assessment) report.
#
# The technical evaluation quantifies the re-identification risk associated with potential attacks, the risk analysis report evaluates the likelihood of such attacks occurring and the resources an adversary would need to carry them out.
#
# [Adapt your PIA report to your data needs](https://python.docs.octopize.io/main/user_guide.html#how-to-create-a-pia-report)

# %%
# download the technical report
runner.download_report("my_report.pdf")

# %%
# download the PIA report, the PIA report is customizable in manager.create_runner()
runner.download_report("my_report_pia.docx", report_type=ReportType.PIA)

# %% [markdown]
# # How to print an error message
# There are multiple types of error and we encourage you to have a look at our [documentation](https://python.docs.octopize.io/latest/user_guide.html#understanding-errors) to understand them.
#
# The most common error is when server validation prevents a job from running.
#
# The following section show how to print an error message.

# %%
runner = manager.create_runner("iris_fail")
runner.add_table("iris", df)

runner.set_parameters("iris", k=500)  # k is too big (bigger than the dataset !)

runner.run(jobs_to_run=[JobKind.standard])

# %%
error_job = runner.get_job(JobKind.standard)
print(error_job.status)
print(error_job.exception)
