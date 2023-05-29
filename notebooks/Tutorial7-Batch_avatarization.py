# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
# ---

# # Tutorial 7: Batch avatarization

# In this tutorial, we will perform the avatarization on data batches. This can be useful if you have a dataset too large to be avatarized in one shot.
#
#
# This is the general workflow of the anonymization using batch.
#
#
#  ![image.png](attachment:image.png)
#

# ## Connection

from avatars.client import ApiClient

# +
import os

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# +
# This is the client that you'll be using for all of your requests
from avatars.models import (
    AvatarizationJobCreate,
    AvatarizationParameters,
    ImputationParameters,
)
from avatars.lib.split import get_split_for_batch
from typing import Any, Dict, List, Tuple
import math

import time

import numpy as np

from avatars.client import ApiClient

from avatars.models import (
    AvatarizationBatchJobCreate,
    AvatarizationBatchParameters,
    AvatarizationBatchResult,
    AvatarizationJob,
    PrivacyMetricsBaseParameters,
    PrivacyMetricsBatchJobCreate,
    PrivacyMetricsBatchParameters,
    PrivacyMetricsJob,
    PrivacyMetricsJobCreate,
    PrivacyMetricsParameters,
    PrivacyBatchDatasetMapping,
    SignalBatchDatasetMapping,
    SignalMetricsBaseParameters,
    SignalMetricsBatchJobCreate,
    SignalMetricsBatchParameters,
)
from avatars.models import ImputeMethod
from avatars.api import (
    download_sensitive_unshuffled_avatar_dataframe_from_batch,
    upload_batch_and_get_order,
    download_avatar_dataframe_from_batch,
)


from avatars.lib.split import get_split_for_batch

# The following are not necessary to
# run avatar but are used in this tutorial
import pandas as pd

# from sklearn.model_selection import train_test_split

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

# ## Load the data
# We will use a subset of the dataset `adult_with_missing`.

df = pd.read_csv("../fixtures/adult_with_missing.csv").head(1000)

# +
# create some batches with from the df

row_limit = 200

training, splits = get_split_for_batch(
    df,
    row_limit=row_limit,
)
# -

# ## Launch batch avatarization
#

# +
dataset_training_id, dataset_split_ids, order = upload_batch_and_get_order(
    client=client,
    training=training,
    splits=splits,
)


batch_job = client.jobs.create_avatarization_batch_job(
    AvatarizationBatchJobCreate(
        parameters=AvatarizationBatchParameters(
            training_dataset_id=dataset_training_id,
            dataset_ids=dataset_split_ids,
            k=20,
            imputation=ImputationParameters(method=ImputeMethod.mean),
        )
    )
)
batch_job = client.jobs.get_avatarization_batch_job(batch_job.id, timeout=40)
batch_job
# -

# ## Launch privacy metric per batch

# +
privacy_job_ref = client.jobs.create_privacy_metrics_batch_job(
    PrivacyMetricsBatchJobCreate(
        parameters=PrivacyMetricsBatchParameters(
            avatarization_batch_job_id=batch_job.id,
            common_parameters=PrivacyMetricsBaseParameters(
                imputation=ImputationParameters(method=ImputeMethod.mean)
            ),
        ),
    )
)
privacy_job = client.jobs.get_privacy_metrics_batch_job(
    privacy_job_ref.id, timeout=100000
)
# you can access batch-averaged metrics
print("Mean metrics")
print(privacy_job.result.mean_metrics)

# you can access the worst metrics over all batches
print("Worst metrics")
print(privacy_job.result.worst_metrics)
# -

# ## Launch signal metrics per batch
#

# +
signal_job_training = client.jobs.create_signal_metrics_batch_job(
    SignalMetricsBatchJobCreate(
        parameters=SignalMetricsBatchParameters(
            avatarization_batch_job_id=batch_job.id,
            common_parameters=SignalMetricsBaseParameters(),
        ),
    )
)
signal_job = client.jobs.get_signal_metrics_batch_job(signal_job_training.id)

print("Mean metrics")
print(signal_job.result.mean_metrics)
# -

# ## Build the anonymized dataset
#
#

# ### Get the shuffled avatar dataframe

avatars = download_avatar_dataframe_from_batch(
    client=client,
    avatarization_batch_result=batch_job.result,
)
avatars.head()

# ###  Get the sensitive unshuffled avatar dataframe

sensitive_avatars = download_sensitive_unshuffled_avatar_dataframe_from_batch(
    client=client, avatarization_batch_result=batch_job.result, order=order
)
sensitive_avatars.head()
