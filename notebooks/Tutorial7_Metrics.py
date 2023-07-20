# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
# ---


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
    ImputeMethod,
    ExcludeCategoricalParameters,
    ExcludeCategoricalMethod,
    RareCategoricalMethod,
    PrivacyMetricsJobCreate,
    PrivacyMetricsParameters,
    SignalMetricsJobCreate,
    SignalMetricsParameters,
)
from avatars.models import ReportCreate

from avatars.api import AvatarizationPipelineCreate
from avatars.processors import ProportionProcessor
from avatars.processors import GroupModalitiesProcessor
from avatars.processors import RelativeDifferenceProcessor
from avatars.processors import PerturbationProcessor
from avatars.processors import ExpectedMeanProcessor
from avatars.processors import DatetimeProcessor

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()
# -

data1 = pd.read_csv("../fixtures/iris.csv")
data2 = pd.read_csv("../fixtures/iris.csv")

dataset1 = client.pandas_integration.upload_dataframe(data1)
dataset2 = client.pandas_integration.upload_dataframe(data2)

dataset1

dataset2

# # Run privacy metrics

privacy_job = client.jobs.create_privacy_metrics_job(
    PrivacyMetricsJobCreate(
        parameters=PrivacyMetricsParameters(
            original_id=dataset1.id,
            unshuffled_avatars_id=dataset2.id,
        )
    ),
    timeout=100,
)

privacy_job = client.jobs.get_privacy_metrics(
    privacy_job.id, timeout=100, per_request_timeout=100
)

privacy_job

# # Run utility metrics

# +
signal_job = client.jobs.create_signal_metrics_job(
    SignalMetricsJobCreate(
        parameters=SignalMetricsParameters(
            original_id=dataset1.id, avatars_id=dataset2.id
        )
    ),
    timeout=100,
)

signal_job = client.jobs.get_signal_metrics(
    signal_job.id, timeout=100, per_request_timeout=100
)
# -

signal_job
