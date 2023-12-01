# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.2
# ---

# # Quickstart - Avatarization with parameters

# ## Connection

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import (
    AvatarizationJobCreate,
    AvatarizationParameters,
    JobStatus,
    ReportCreate,
    PrivacyMetricsJobCreate,
    PrivacyMetricsParameters,
    SignalMetricsJobCreate,
    SignalMetricsParameters,
)

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io
import os

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")
print(url)
# -

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# ## Loading data

df = pd.read_csv("../fixtures/wbcd.csv")
dataset = client.pandas_integration.upload_dataframe(df)

# ## Analyze your data

dataset = client.datasets.analyze_dataset(dataset.id)
print(f"Lines: {dataset.nb_lines}, dimensions: {dataset.nb_dimensions}")

# ## Creating and launching an avatarization job and metrics

# +
avatarization_job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=10, dataset_id=dataset.id),
    )
)

avatarization_job = client.jobs.get_avatarization_job(
    avatarization_job.id, timeout=1800
)
print(avatarization_job.status)
# -

# ## Calculate Privacy Metrics

privacy_job = client.jobs.create_privacy_metrics_job(
    PrivacyMetricsJobCreate(
        parameters=PrivacyMetricsParameters(
            original_id=dataset.id,
            unshuffled_avatars_id=avatarization_job.result.sensitive_unshuffled_avatars_datasets.id,
            closest_rate_percentage_threshold=0.3,
            closest_rate_ratio_threshold=0.3,
            known_variables=[dataset.columns[0].label, dataset.columns[1].label],
            target=dataset.columns[-1].label,
        ),
    )
)

privacy_job = client.jobs.get_privacy_metrics(privacy_job.id, timeout=1800)
print(privacy_job.status)
print("*** Privacy metrics ***")
for metric in privacy_job.result:
    print(metric)

# ## Calculate Utility Metrics

signal_job = client.jobs.create_signal_metrics_job(
    SignalMetricsJobCreate(
        parameters=SignalMetricsParameters(
            original_id=dataset.id,
            avatars_id=avatarization_job.result.avatars_dataset.id,
        ),
    )
)

signal_job = client.jobs.get_signal_metrics(signal_job.id, timeout=1800)
print(signal_job.status)
print("*** Utility metrics ***")
for metric in signal_job.result:
    print(metric)

# ## Retrieve avatars

# +
# Download the avatars as a pandas dataframe
avatars_df = client.pandas_integration.download_dataframe(
    avatarization_job.result.avatars_dataset.id
)

avatars_str = avatars_df.to_csv()
with open("./avatar_output.csv", "wb") as f:
    f.write(avatars_str.encode())
# -

# ## Retrieving the avatarization report

report = client.reports.create_report(
    ReportCreate(
        avatarization_job_id=avatarization_job.id,
        privacy_job_id=privacy_job.id,
        signal_job_id=signal_job.id,
    ),
    timeout=240,
)
print(report)

# +
result = client.reports.download_report(id=report.id)

with open("./my_avatarization_report.pdf", "wb") as f:
    f.write(result)
