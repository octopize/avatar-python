# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
# ---

# # Tutorial 1: A basic avatarization

# In this tutorial, we will connect to a server to perform the avatarization of a dataset that does not require any pre-processing. We'll retrieve the anonymized dataset and the associated avatarization report.

# ## Connection

# +
import os

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters
from avatars.models import ReportCreate

import pandas as pd
import io

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)
# -

# Verify that we can connect to the API server
client.health.get_health()

# Verify that the client is compatible.
client.compatibility.is_client_compatible()

# ## Loading data

# We recommend loading your csv file as a pandas dataframe. It enables you to check your data before avatarization and to pre-process it if required.
#
# In this tutorial, we use the simple and well-known `iris` dataset to demonstrate the main steps of an avatarization.

df = pd.read_csv("../fixtures/iris.csv")

df

dataset = client.pandas_integration.upload_dataframe(df)
print(dataset)

# The data has now been loaded onto the server.
#
# Note that it is also possible to directly load a csv file without using pandas.

# +
filename = "../fixtures/iris.csv"

with open(filename, "r") as f:

    dataset = client.datasets.create_dataset(request=f)
print(dataset)
# -

# ## Analyze your data
#
# A tool to analyze the data prior to an avatarization is provided. It computes several statistics that can be useful to:
# - confirm that the data loaded is as expected and
# - give insight on potential transformation to the data that are required (this will be covered in later tutorials)

dataset

dataset = client.datasets.analyze_dataset(dataset.id)
while dataset.summary is None:
    dataset = client.datasets.get_dataset(dataset.id)

print(dataset.summary)

for var in dataset.summary.stats:
    print("---------")
    for stat in var:
        print(stat)

# ## Creating and launching an avatarization job with metrics

# +
job = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=20, dataset_id=dataset.id),
    )
)

print(job.status)
# -

# ## Retrieving the completed avatarization job

# +
job = client.jobs.get_avatarization_job(id=job.id)

print(job.status)
# -

# ## Retrieving the avatars

# +
# Download the avatars as a string
avatars_str = client.datasets.download_dataset(job.result.avatars_dataset.id)

# Download the avatars as a pandas dataframe
avatars_df = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)
# -

print(avatars_str)

print(avatars_df)

# ## Retrieving the utility and privacy metrics

# Because this dataset did not require any pre-processing or post-processing outside the avatarization job, the metrics calculated at the end of the avatarization job can directly be used.

privacy_metrics = job.result.privacy_metrics
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

utility_metrics = job.result.signal_metrics
print("*** Utility metrics ***")
for metric in utility_metrics:
    print(metric)

# ## Creating and launching an avatarization job without metrics

# +
avatarization_job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=20, dataset_id=dataset.id),
    )
)


avatarization_job = client.jobs.get_avatarization_job(avatarization_job.id, timeout=10)
print(job.status)
print(job.result)  # there is no metrics

# +
from avatars.models import PrivacyMetricsJobCreate, PrivacyMetricsParameters

privacy_job = client.jobs.create_privacy_metrics_job(
    PrivacyMetricsJobCreate(
        parameters=PrivacyMetricsParameters(
            original_id=dataset.id,
            unshuffled_avatars_id=job.result.sensitive_unshuffled_avatars_datasets.id,
            closest_rate_percentage_threshold=0.3,
            closest_rate_ratio_threshold=0.3,
            known_variables=[
                "sepal.length",
                "petal.length",
            ],
            target="variety",
            seed=42,
        ),
    )
)

privacy_job = client.jobs.get_privacy_metrics(privacy_job.id, timeout=10)

print(privacy_job.status)
print(privacy_job.result)

# +
from avatars.models import SignalMetricsJobCreate, SignalMetricsParameters

signal_job = client.jobs.create_signal_metrics_job(
    SignalMetricsJobCreate(
        parameters=SignalMetricsParameters(
            original_id=dataset.id,
            avatars_id=job.result.avatars_dataset.id,
            seed=42,
        ),
    )
)

signal_job = client.jobs.get_signal_metrics(signal_job.id, timeout=10)
print(signal_job.status)
print(signal_job.result)
# -

# ## Retrieving the avatarization report

# +
report = client.reports.create_report(
    ReportCreate(
        avatarization_job_id=avatarization_job.id,
        privacy_job_id=privacy_job.id,
        signal_job_id=signal_job.id,
    ),
    timeout=10,
)
result = client.reports.download_report(id=report.id)

with open("./my_avatarization_report.pdf", "wb") as f:
    f.write(result)
# -

# The report is now generated and available on your machine

# *In the next tutorial, we will show how to parameterize an avatarization.*
