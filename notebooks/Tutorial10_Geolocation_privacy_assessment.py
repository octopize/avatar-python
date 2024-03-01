# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Tutorial 10: Geolocation privacy assessment

# In this tutorial, we demonstrate how to run a privacy assessment on geolocation trace data using an original dataset and a treated version of the same data.

# ## Connection

# +
import os
import matplotlib.pyplot as plt
import seaborn as sns

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# +
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import (
    AvatarizationJobCreate,
    AvatarizationParameters,
    GeolocationDensityParameters,
    GeolocationFeatures,
    GeolocationFeaturesParameters,
    JobStatus,
    PointOfInterest,
    PrivacyMetricsGeolocationJobCreate,
    PrivacyMetricsGeolocationParameters,
    PrivacyMetricsGeolocationScenario,
    ReportGeolocationPrivacyCreate,
    SignalPosition,
)

import pandas as pd
import io

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# +
# Verify that we can connect to the API server
client.health.get_health()

# Verify that the client is compatible.
client.compatibility.is_client_compatible()
# -

# ## Loading data

# In this tutorial, we use the Porto taxis dataset, an open dataset often used to demonstrate geolocation data functionalities. The dataset is prepared to fit the format required by the geolocation privacy assessment feature, i.e. it contains the following columns: `id`, `t`, `lat` and `lon`.

original_df = pd.read_csv("../fixtures/porto_taxi_200.csv")
original_df

# To demonstrate the privacy assessment, we will use two versions of the same data that have been altered in order to protect the privacy of the individuals, i.e. the drivers of the vehicles. Each version is treated following two distinct approaches:
# - the first dataset (`trimmed_df`) is obtained by trimming / removing the start and end points of each trip.
# - the second dataset (`noised_df`) is also obtained by trimming trips' start and end but noise is also added to each point.
#
# It is important to note that for the privacy assessment to be possible, the identifier (column `id`) need to be consistent across the datasets.

trimmed_df = pd.read_csv("../fixtures/porto_taxi_trimmed_200.csv")
trimmed_df

noised_df = pd.read_csv("../fixtures/porto_taxi_noised_200.csv")
noised_df

# We provide below a view of all the original traces followed by a visualisation of a same trip in its original, trimmed and noised version.

plt.figure(figsize=(20, 20))
sns.scatterplot(data=original_df, x="lon", y="lat", hue="id", legend=False)
plt.title("Original traces")
plt.show

# +
selected_id = 1

plt.figure(figsize=(10, 10))
sns.scatterplot(
    data=original_df[original_df["id"] == selected_id],
    x="lon",
    y="lat",
    label="Original",
)
sns.scatterplot(
    data=trimmed_df[trimmed_df["id"] == selected_id], x="lon", y="lat", label="Trimmed"
)
sns.scatterplot(
    data=noised_df[noised_df["id"] == selected_id], x="lon", y="lat", label="Noised"
)
plt.title(
    f"Example geolocation trace (id={selected_id}) and its trimmed and noised versions"
)
plt.legend()
plt.show
# -

# ## Run a geolocation privacy assessment

# ### Upload datasets

original_dataset = client.pandas_integration.upload_dataframe(original_df)
print(f"Dataset {original_dataset.id} loaded")
trimmed_dataset = client.pandas_integration.upload_dataframe(trimmed_df)
print(f"Dataset {trimmed_dataset.id} loaded")
noised_dataset = client.pandas_integration.upload_dataframe(noised_df)
print(f"Dataset {noised_dataset.id} loaded")

# ### Create scenarios
#
# A privacy assessment for geolocation data requires the definition of potentially multiple scenarios.
# A scenario defines some attacks that will be considered during the assessment. One scenario contains the following parameters:
# - `projection_parameters` defines the method of projection (or representation) of the data that will be used to evaluate the level of protection against **singling-out attacks**. For example, an attack can attempt re-identification using trace density information (this projection is set by using `GeolocationDensityParameters`). An alternative is for re-identification of traces to be performed from calculated features such as mean speed, trip duration ... This projection can be chosen by setting the parameters with `GeolocationFeaturesParameters`.
# - `known_features` defines a calculated feature that may be known to an attacker and that could be used to link the anonymized data with data from an external source. This attack is a **feature-based linkability attack**.
# - `target_feature` defines a calculated feature that could be considered as sensitive and should be protected against **feature-based inference attacks**. Such attack would use the `known_features` to infer the `target_feature`.
# - `known_signal_position` defines a part of the trip that could be known to an attacker (i.e. the start, middle or end of a trip). Attempt to re-associate anonymized trips to their original counterparts only using this information is considered as a **trace-based linkability attack**.
# - `target_signal_poi` defines the point of interest (POI) that could be considered as a target for an attacker in the context of a **trace-based inference attack**. It can be the start or the end of a trip.
# - `inference_metric_threshold` defines the distance under which a prediction on a target point of interest will be considered as a successful prediction by the attacker. Setting a large threshold will increase the expected level of protection.
#
# The ability to define many scenarios ensure that the data can be looked from different angles and that the privacy assessment cover many types of attacks. There is no limit on the number of scenarios that can be defined.
#
# Note that only `projection_parameters` must be set in a scenario, the remaining fields are optional.
#
# The example below defines 3 scenarios.

scenarios = [
    # Scenario 0
    PrivacyMetricsGeolocationScenario(
        projection_parameters=GeolocationDensityParameters(),
        known_features=[
            GeolocationFeatures.duration,
            GeolocationFeatures.length,
        ],
        target_feature=GeolocationFeatures.speed,
        known_signal_position=SignalPosition.start,
        target_signal_poi=PointOfInterest.end,
        inference_metric_threshold=20000,
    ),
    # Scenario 1
    PrivacyMetricsGeolocationScenario(
        projection_parameters=GeolocationFeaturesParameters()
    ),
    # Scenario 2
    PrivacyMetricsGeolocationScenario(
        projection_parameters=GeolocationFeaturesParameters(),
        known_features=[
            GeolocationFeatures.speed,
        ],
        target_feature=GeolocationFeatures.length,
    ),
]

# ### Launch the job
#
# Similar to avatarization, a privacy assessment job is first created by specifying the original data, the unshuffled treated data and the scenarios.

# +
parameters = PrivacyMetricsGeolocationParameters(
    original_dataset_id=original_dataset.id,
    unshuffled_avatar_dataset_id=trimmed_dataset.id,
    scenarios=scenarios,
)

privacy_job_trimmed = client.jobs.create_privacy_metrics_geolocation_job(
    PrivacyMetricsGeolocationJobCreate(parameters=parameters)
)
# -

# The job is retrieved with `get_privacy_metrics_geolocation_job`. Note that the addition of scenarios will increase the time required for the job to complete and so the timeout parameters may need to be adapted to get a `success` status.

privacy_job_trimmed = client.jobs.get_privacy_metrics_geolocation_job(
    privacy_job_trimmed.id, timeout=300
)
privacy_job_trimmed.status

# The privacy job object retrieved contains the privacy metric results. Those can be accessed using `privacy_job_trimmed.result`. Alternatively or complementarily, a report can be generated to improve their readability, for better sharing or for audit purposes.

# ### Create a geolocation privacy assessment automatic report

report = client.reports.create_geolocation_privacy_report(
    ReportGeolocationPrivacyCreate(
        dataset_id=original_dataset.id,
        avatars_dataset_id=trimmed_dataset.id,
        privacy_job_id=privacy_job_trimmed.id,
    ),
    timeout=30,
)
result = client.reports.download_report(id=report.id)

with open("./my_geolocation_privacy_assessment_report_trimmed.pdf", "wb") as f:
    f.write(result)

# ## Comparing the two treated dataset versions
#
# To further demonstrate how the geolocation privacy assessment can be used, we run a second job using the second dataset treated with the noise addition approach. This will enable a comparison of both treated datasets.

# +
parameters = PrivacyMetricsGeolocationParameters(
    original_dataset_id=original_dataset.id,
    unshuffled_avatar_dataset_id=noised_dataset.id,
    scenarios=scenarios,
)

privacy_job_noised = client.jobs.create_privacy_metrics_geolocation_job(
    PrivacyMetricsGeolocationJobCreate(parameters=parameters)
)
# -

privacy_job_noised = client.jobs.get_privacy_metrics_geolocation_job(
    privacy_job_noised.id, timeout=300
)
privacy_job_noised.status

# +
report = client.reports.create_geolocation_privacy_report(
    ReportGeolocationPrivacyCreate(
        dataset_id=original_dataset.id,
        avatars_dataset_id=trimmed_dataset.id,
        privacy_job_id=privacy_job_noised.id,
    ),
    timeout=30,
)
result = client.reports.download_report(id=report.id)

with open("./my_geolocation_privacy_assessment_report_noised.pdf", "wb") as f:
    f.write(result)

# +
trimmed_hidden_rate = privacy_job_trimmed.result.privacy_metrics_per_scenario[
    0
].privacy_metrics.hidden_rate
noised_hidden_rate = privacy_job_noised.result.privacy_metrics_per_scenario[
    0
].privacy_metrics.hidden_rate

print(
    f"The hidden rate obtained in the first defined scenario is {trimmed_hidden_rate}% for the data that was trimmed while it is {noised_hidden_rate}% for the data treated with noise addition."
)
# -

# By looking at the privacy metrics gathered in the `privacy_job_trimmed.result` and `privacy_job_noised.result` objects or the two reports generated, we can see that one treatment resulted in a much better level of privacy (`noised`) while the other treatment (`trimmed`) did not meet all privacy target, in particular in terms of hidden rate)
