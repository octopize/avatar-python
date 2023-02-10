# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
# ---

# # Quickstart - Simple avatarization

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters, JobStatus
from avatars.models import ReportCreate
from avatars.models import PrivacyMetricsJobCreate, PrivacyMetricsParameters
from avatars.models import SignalMetricsJobCreate, SignalMetricsParameters

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io
import os
import datetime

# -

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")
print(url)

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# ## Loading data

df = pd.read_csv("../fixtures/iris.csv")
dataset = client.pandas_integration.upload_dataframe(df)

# ## Analyze your data

while dataset.summary is None:
    dataset = client.datasets.analyze_dataset(dataset.id)
print(f"Lines: {dataset.nb_lines}, dimensions: {dataset.nb_dimensions}")

# ## Creating and launching a avatarization job and metrics

avatarization_job = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=20, dataset_id=dataset.id),
    )
)
avatarization_job = client.jobs.get_avatarization_job(avatarization_job.id, timeout=10)

# ## View Privacy & Utility metrics

privacy_metrics = avatarization_job.result.privacy_metrics
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

utility_metrics = avatarization_job.result.signal_metrics
print("*** Utility metrics ***")
for metric in utility_metrics:
    print(metric)

# ## Retrieves avatars

# +
# Download the avatars as a string
avatars_str = client.datasets.download_dataset(
    avatarization_job.result.avatars_dataset.id
)

# Download the avatars as a pandas dataframe
avatars_df = client.pandas_integration.download_dataframe(
    avatarization_job.result.avatars_dataset.id
)
