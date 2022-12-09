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

# # Tutorial 1: A basic avatarization

# In this tutorial, we will connect to a server to perform the avatarization of a dataset that does not require any pre-processing. We'll retrieve the anonymized dataset and the associated avatarization report.

# ## Connection

# +
import os

url=os.environ.get("AVATAR_BASE_URL")
username=os.environ.get("AVATAR_USERNAME")
password=os.environ.get("AVATAR_PASSWORD")

print(os.environ.get("VIRTUAL_ENV"))

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters
from avatars.models import ReportCreate

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(
    username=username, password=password
)

# Verify that we can connect to the API server
client.health.get_health()
# -

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

dataset = client.datasets.analyze_dataset(dataset.id, timeout = 1000)

print(dataset.summary)

for var in dataset.summary.stats:
    print('---------')
    for stat in var:
        print(stat)

# ## Creation of an avatarization job

# +
job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k = 5,
            dataset_id=dataset.id
        ),
    )
)

print(job.status)
# -

# ## Launching the avatarization

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

# ## Retrieving the avatarization report

# +
report = client.reports.create_report(ReportCreate(job_id=job.id))
result = client.reports.download_report(id=report.id)

with open("./my_avatarization_report.pdf", "wb") as f:
    f.write(result)
# -

# The report is now generated and available on your machine

# *In the next tutorial, we will show how to parameterize an avatarization.*
