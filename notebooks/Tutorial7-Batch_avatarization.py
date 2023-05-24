# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
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
print(df_1.shape)
df = pd.concat([df_1 for i in range(4)])
print(df.shape)

# +
from typing import Any, Dict, List
import math

import numpy as np

from avatars.models import (
    AvatarizationJob,
    PrivacyMetricsJob,
    PrivacyMetricsJobCreate,
    PrivacyMetricsParameters,
)


def get_row_with_unique_modality(df: pd.DataFrame) -> pd.DataFrame:
    categorical_columns = df.dtypes[df.dtypes == "object"].index.to_list()
    df[categorical_columns] = df[categorical_columns].fillna("NAN")
    counts = df[categorical_columns].apply(pd.Series.value_counts)

    ind = counts[(counts == 1).any(axis=1)].index

    unique_modality_value_count_per_column = counts[(counts == 1).any(axis=1)]
    is_column_with_outliers = ~unique_modality_value_count_per_column.isna().all(axis=0)
    column_with_outliers = is_column_with_outliers[is_column_with_outliers].index

    outliers = df[(df[column_with_outliers].isin(ind)).any(axis=1)]
    return outliers


def get_split_for_batch(
    df: pd.DataFrame,
    row_limit: int,
):
    number_of_split = math.ceil(len(df) / row_limit)

    outliers = get_row_with_unique_modality(df)
    df_without_outliers = df.drop(index=outliers.index).reset_index(drop=True)
    shuffled = df_without_outliers.sample(frac=1)
    splits = np.array_split(shuffled, number_of_split)

    first_split = splits[0].reset_index(drop=True)

    samples = first_split.iloc[: len(outliers), :]
    df_ref = first_split.iloc[len(outliers) :, :]
    splits[0] = pd.concat([df_ref, outliers])

    samples_splited = np.array_split(samples, number_of_split)
    splits = [
        pd.concat([sample1, sample2]).reset_index(drop=True)
        for sample1, sample2 in zip(splits, samples_splited)
    ]
    return splits


def get_avatar_using_batch(
    splits: List[pd.DataFrame], parameters: Dict[str, Any]
) -> List[AvatarizationJob]:

    print(f"Initialization: Batch 1/{len(splits)}")
    start = time.time()

    dataset_ref = client.pandas_integration.upload_dataframe(splits[0], timeout=10)
    reference_job = client.jobs.create_avatarization_job(
        AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset_ref.id, **parameters),
        )
    )
    reference_job_result = client.jobs.get_avatarization_job(
        id=reference_job.id, timeout=10000000
    )
    print("time", time.time() - start)

    batch_jobs = []
    for i in range(1, len(splits)):
        print(f"Iteration - Batch {i+1}/{len(splits)}")
        start = time.time()

        dataset_batch = client.pandas_integration.upload_dataframe(
            splits[i], timeout=10
        )
        batch_job = client.jobs.add_avatarization_batch_job(
            reference_job_id=reference_job.id, dataset_id=dataset_batch.id
        )
        batch_jobs.append(batch_job)
        print("time", time.time() - start)
    job_results = [reference_job_result]

    for job in batch_jobs:
        start = time.time()
        print(f"try to get avatarization jobs {job.id}")
        batch_job_result = client.jobs.get_avatarization_job(
            id=job.id, timeout=10000000
        )
        job_results.append(batch_job_result)
        print("time", time.time() - start)

    return job_results


import time


# def get_avatar_using_batch_but_wrongly(df: pd.DataFrame, row_limit: int, parameters: Dict[str, Any]) -> List[AvatarizationJob]:
#     number_of_split = math.ceil(len(df) / row_limit)

#     outliers = get_outliers(df)
#     df_without_outliers = df.drop(index= outliers.index).reset_index(drop=True)
#     shuffled = df_without_outliers.sample(frac=1)
#     splits = np.array_split(shuffled, number_of_split)

#     first_split = splits[0].reset_index(drop=True)

#     samples = first_split.iloc[: len(outliers), :]
#     df_ref = first_split.iloc[len(outliers) : , :]
#     splits[0] = pd.concat([df_ref, outliers])

#     samples_splited = np.array_split(samples, number_of_split)
#     splits = [pd.concat([sample1, sample2]).reset_index(drop=True) for sample1, sample2 in zip( splits, samples_splited )]

#     print(f"Initialization: Batch 1/{len(splits)}")
#     start = time.time()
#     dataset_ref = client.pandas_integration.upload_dataframe(splits[0], timeout = 10)
#     reference_job = client.jobs.create_avatarization_job(
#         AvatarizationJobCreate(
#             parameters=AvatarizationParameters(dataset_id=dataset_ref.id, **parameters),
#         )
#     )
#     reference_job_result = client.jobs.get_avatarization_job(id=reference_job.id, timeout=10000000)
#     print("time", time.time() - start)

#     job_results = [reference_job_result]

#     for i in range(1, len(splits)):
#         start = time.time()
#         dataset_batch = client.pandas_integration.upload_dataframe(splits[i], timeout = 10)
#         batch_job = client.jobs.add_avatarization_batch_job(reference_job_id=reference_job.id, dataset_id=dataset_batch.id)
#         print(f"Iteration - Batch {i+1}/{len(splits)}")
#         batch_job_result = client.jobs.get_avatarization_job(id=batch_job.id, timeout=10000000)
#         job_results.append(batch_job_result)

#         print("time", time.time() - start)
#     return job_results


# def get_privacy_metrics_with_batch_but_wrongly(avatarization_jobs: List[AvatarizationJob], parameters: Dict[str, Any])-> List[PrivacyMetricsJob]:
#     # Initialization
#     print(f"Initialization - Batch 1/{len(avatarization_jobs)}")
#     start = time.time()
#     privacy_job_ref = client.jobs.create_privacy_metrics_job(
#         PrivacyMetricsJobCreate(
#             parameters=PrivacyMetricsParameters(
#                 original_id=avatarization_jobs[0].parameters.dataset_id,
#                 unshuffled_avatars_id=avatarization_jobs[0].result.sensitive_unshuffled_avatars_datasets.id,
#                 **parameters,
#             ),
#         )
#     )
#     privacy_job = client.jobs.get_privacy_metrics(privacy_job_ref.id, timeout=100000)
#     print(time.time() - start)
#     privacy_results = [privacy_job]
#     # Iterate
#     for i in range(1, len(avatarization_jobs)):
#         start = time.time()
#         print(f"Iteration - Batch {i+1}/{len(avatarization_jobs)}")
#         privacy_batch = client.jobs.create_privacy_metrics_batch_job(reference_privacy_batch__job_id = privacy_job_ref.id,avatarization_batch_job_id =avatarization_jobs[i].id)
#         privacy_batch = client.jobs.get_privacy_metrics(privacy_batch.id, timeout=1000000)
#         privacy_results.append(privacy_batch)
#         print(time.time() - start)
#     return privacy_results


def get_privacy_metrics_with_batch(
    avatarization_jobs: List[AvatarizationJob], parameters: Dict[str, Any]
) -> List[PrivacyMetricsJob]:
    # Initialization
    print(f"Initialization - Batch 1/{len(avatarization_jobs)}")
    start = time.time()
    privacy_job_ref = client.jobs.create_privacy_metrics_job(
        PrivacyMetricsJobCreate(
            parameters=PrivacyMetricsParameters(
                original_id=avatarization_jobs[0].parameters.dataset_id,
                unshuffled_avatars_id=avatarization_jobs[
                    0
                ].result.sensitive_unshuffled_avatars_datasets.id,
                **parameters,
            ),
        )
    )
    privacy_job = client.jobs.get_privacy_metrics(privacy_job_ref.id, timeout=100000)
    print(time.time() - start)

    privacy_results = [privacy_job]
    privacy_jobs = []
    # Iterate
    for i in range(1, len(avatarization_jobs)):
        start = time.time()
        print(f"Batch {i+1}/{len(avatarization_jobs)}")
        privacy_batch = client.jobs.create_privacy_metrics_batch_job(
            reference_privacy_batch__job_id=privacy_job_ref.id,
            avatarization_batch_job_id=avatarization_jobs[i].id,
        )
        privacy_jobs.append(privacy_batch)
        print(time.time() - start)
    for job in privacy_jobs:
        start = time.time()
        print("try to get privacy jobs ")
        privacy_result = client.jobs.get_privacy_metrics(job.id, timeout=1000000)
        privacy_results.append(privacy_result)
        print(time.time() - start)
    return privacy_results


# -

#

# +
RowLimit = 50000

splits = get_avatar_using_batch(
    df,
    parameters={"k": 20, "imputation": ImputationParameters(method="mean")},
    row_limit=RowLimit,
)


splits
# -

splits = get_avatar_using_batch_but_wrongly(
    df,
    parameters={"k": 20, "imputation": ImputationParameters(method="mean")},
    row_limit=RowLimit,
)
splits

jobs = client.jobs.find_all_jobs_by_user()
print(len(jobs))
# for job in jobs:
#     print(job)

# +
from avatars.models import JobStatus

for elem in jobs:
    if elem.status == JobStatus.pending:
        print(elem.id, "was deleted")
        client.jobs.cancel_job(elem.id)

# +
privacy_results = get_privacy_metrics_with_batch(
    splits,
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

# +
privacy_results = get_privacy_metrics_with_batch_but_wrongly(
    splits,
    parameters={
        "closest_rate_percentage_threshold": 0.3,
        "closest_rate_ratio_threshold": 0.3,
        "known_variables": [
            "age",
            "workclass",
        ],
        "imputation": ImputationParameters(method="mean"),
        "target": "income",
        "seed": 42,
    },
)

privacy_results
# -

privacy_job = client.jobs.create_privacy_metrics_job(
    PrivacyMetricsJobCreate(
        parameters=PrivacyMetricsParameters(
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

df_batch.shape

dataset_ref = client.pandas_integration.upload_dataframe(df_ref, timeout=100)
dataset_ref.id

# +
import time

start = time.time()
job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=20,
            dataset_id=dataset_ref.id,
            imputation=ImputationParameters(method="mean"),
        ),
    )
)
print(job.id)
result = client.jobs.get_avatarization_job(id=job.id, timeout=100)
print(result.status)
print(time.time() - start)
# -

result = client.jobs.get_avatarization_job(id=job.id, timeout=10)
print(result.status)
result


# +
import time

start = time.time()
batch_job = client.jobs.add_avatarization_batch_job(
    reference_job_id=job.id, dataset_id=dataset_batch.id
)
batch_job = client.jobs.get_avatarization_job(id=batch_job.id, timeout=10)
print(job.status)
print(time.time() - start)

# +
batch_job = client.jobs.get_avatarization_job(id=batch_job.id, timeout=10)

print(job.id)

print(batch_job.id)
print(batch_job.status)
# -

avatars_batch = client.pandas_integration.download_dataframe(
    batch_job.result.avatars_dataset.id
)
avatars_batch.shape
