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

# In this tutorial, we will perform the avatarization on batch of data. This can be useful if you have to much data that can be avatarized in one shot.
#
# # TODO: add a schema of the process
#

# ## Connection

# +
import warnings

warnings.filterwarnings("ignore")

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
)
from avatars.lib.split import get_split_for_batch

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
from sklearn.model_selection import train_test_split

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

df_1 = pd.read_csv("../fixtures/adult_with_cities.csv")
df = pd.concat([df_1 for i in range(4)])

# +
from typing import Any, Dict, List, Tuple
import math

import time


import numpy as np

from avatars.models import (
    AvatarizationBatchJobCreate,
    AvatarizationBatchParameters,
    AvatarizationBatchResult,
    AvatarizationJob,
    PrivacyMetricsBatchJobCreate,
    PrivacyMetricsBatchParameters,
    PrivacyMetricsJob,
    PrivacyMetricsJobCreate,
    PrivacyMetricsParameters,
    PrivacyMetricsPerBatchParameters,
    PrivacyMetricsReferenceParameters,
    SignalMetricsBatchJobCreate,
    SignalMetricsBatchParameters,
    SignalMetricsReferenceParameters,
)

from avatars.lib.split import get_split_for_batch


def get_avatar_using_batch(
    reference_df: pd.DataFrame, splits: List[pd.DataFrame], parameters: Dict[str, Any]
) -> AvatarizationBatchResult:

    start = time.time()

    dataset_ref = client.pandas_integration.upload_dataframe(reference_df, timeout=10)
    dataset_splited_ids = [
        client.pandas_integration.upload_dataframe(split, timeout=10).id
        for split in splits
    ]
    batch_job = client.jobs.create_avatarization_batch_job(
        AvatarizationBatchJobCreate(
            parameters=AvatarizationBatchParameters(
                reference_dataset_id=dataset_ref.id,
                dataset_ids=dataset_splited_ids,
                **parameters,
            )
        )
    )
    batch_job = client.jobs.get_avatarization_batch_job(batch_job.id, timeout=10000)
    print("time", time.time() - start)

    return batch_job


def get_privacy_metrics_with_batch(
    batch_job: AvatarizationBatchResult, parameters: Dict[str, Any]
) -> List[PrivacyMetricsJob]:
    # Initialization
    start = time.time()
    privacy_job_ref = client.jobs.create_privacy_metrics_batch_job(
        PrivacyMetricsBatchJobCreate(
            parameters=PrivacyMetricsBatchParameters(
                avatarization_batch_job_id=batch_job.id,
                reference_parameters=PrivacyMetricsReferenceParameters(**parameters),
            ),
        )
    )
    print(privacy_job_ref.id)
    privacy_job = client.jobs.get_privacy_metrics_batch_job(
        privacy_job_ref.id, timeout=100000
    )
    print(time.time() - start)

    return privacy_job


def get_signal_metrics_with_batch(
    batch_job: AvatarizationBatchResult, parameters: Dict[str, Any]
) -> List[PrivacyMetricsJob]:
    # Initialization
    start = time.time()
    signal_job_ref = client.jobs.create_signal_metrics_batch_job(
        SignalMetricsBatchJobCreate(
            parameters=SignalMetricsBatchParameters(
                avatarization_batch_job_id=batch_job.id,
                reference_parameters=SignalMetricsReferenceParameters(**parameters),
            ),
        )
    )
    signal_job = client.jobs.get_signal_metrics_batch_job(signal_job_ref.id)
    print(time.time() - start)

    return signal_job


# -

#

df.dtypes

# +
RowLimit = 50000

ref, splits = get_split_for_batch(
    df,
    row_limit=RowLimit,
)


print(len(splits[0]))

# 44875 -> 35974
# -

splits = get_avatar_using_batch(
    reference_df=ref,
    splits=splits,
    parameters={"k": 20, "imputation": ImputationParameters(method="mean")},
)
splits

client.jobs.find_all_jobs_by_user(nb_days=1)

# +
privacy_results = get_privacy_metrics_with_batch(
    batch_job=splits,
    parameters={
        "closest_rate_percentage_threshold": 0.3,
        "closest_rate_ratio_threshold": 0.3,
        "known_variables": [
            "age",
            "workclass",
        ],
        "target": "income",
        "imputation": ImputationParameters(method="mean"),
        "seed": 42,
    },
)

privacy_results
# -

privacy_job = client.jobs.get_privacy_metrics_batch_job(
    "2aa81d1a-e2b3-4221-b930-4b64723e1976", timeout=100000
)

# +
signal_results = get_signal_metrics_with_batch(
    batch_job=splits,
)

signal_results
# -
