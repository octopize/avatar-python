# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.16.2
# ---

# # Tutorial 4: Client-side processors

# In this tutorial, we will learn how to prepare the data prior to running an avatarization by using processors on your local machine.
#
# This step is necessary in some cases to handle and preserve data characteristics that are not natively handled by the avatarization or its embedded processors.
#
# We'll also show how custom client-side processors can be defined to integrate domain knowledge into an avatarization.

# ## Principles

# ![pipeline](img/pipeline.png)

# ## Connection

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

# ## A helper processor to reduce the number of modalities

# We have seen in the previous tutorial one approach to handle categorical variables with large cardinality. We propose here an alternative way of doing this using a client-side processor.
#
# This processor will group modalities together to ensure the target variable has a requested number of modalities. The least represented modalities will be brought together under a `other` modality. Note that this transformation is irreversible (the original value cannot be infered from `other`).
#
# Because this is an irreversible operation, this transformation of the data should be done outside the pipeline. The transformed data will be used as a basis for comparison when computing utility and privacy metrics.

df = (
    pd.read_csv("../fixtures/adult_with_cities.csv")
    .head(1000)
    .drop(["native-country"], axis=1)
)
dataset = client.pandas_integration.upload_dataframe(df)
print(df.shape)
df.head()

# After loading the data, we decide we wish to reduce the number of modalities for the variable `city` which contains originally over 80 distinct values.

df["city"].value_counts()

group_modalities_processor = GroupModalitiesProcessor(
    min_unique=10,  # number of modalities for a variable to be considered for grouping
    global_threshold=25,  # if considered for grouping, number of individuals in modality to preserve it
    new_category="other",
)

df_preprocessed = group_modalities_processor.preprocess(df)

# Once the group modality processor has been applied, we can confirm that the number of modalities for the `city` variables has been reduced

df_preprocessed["city"].value_counts()

# +
# %%time
dataset = client.pandas_integration.upload_dataframe(df_preprocessed)

result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5),
        ),
        processors=[],
        df=df,
    ),
    timeout=1000,
)
# -

result

avatars = result.post_processed_avatars
avatars.head(3)

avatars["city"].value_counts()

# We observe that the avatars produced have a reduced number of cities and an extra `other` modality for the `city` variable. Note that the use of a client-side processor made the transformation of the data straightforward.
#
# The calculation of the metrics has been performed during the execution of the pipeline. Results can be obtained as shown below.

# +
privacy_metrics = result.privacy_metrics
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

utility_metrics = result.signal_metrics
print("\n*** Utility metrics ***")
for metric in utility_metrics:
    print(metric)
# -

# ## Modeling inter-variables constraints with processors

# We will now use two processors to enforce inter-variable constraints.
#
# The two processors we will now apply are processors that temporarily transform the data in order to improve the avatarization. This means that they both contain a `preprocess` step and a `postprocess` step, ensuring that the effect of the `preprocess` action can be reversed via the use of the `postprocess` action.
#
# These processors will be used to demonstrate the implementation of the pipeline tool that automates the use of processors, the avatarization and the metric computation in a single command.
#

df = pd.read_csv("../fixtures/epl.csv")

# Prior to applying processors, it is important to check `dtypes` and eventually convert date variables to a `datetime` format using `pandas.to_datetime` function.

df.dtypes

df["career_start_date"] = pd.to_datetime(
    df["career_start_date"], format="%Y-%m-%d %H:%M:%S"
)
df["club_signing_date"] = pd.to_datetime(
    df["club_signing_date"], format="%Y-%m-%d %H:%M:%S"
)

# ### Proportions
#
# Variables may have relationships in which one or many variables can be represented as a proportion of another. In order to best preserve this type of relationships during avatarization, it is recommended to express such variables as proportions. To do so, the proportion processor can be used.
#
# In our example, the `ProportionProcessor` can be used, because `minutes_in_game` is the sum of `minutes_played_home`, `minutes_played_away` and `minutes_on_bench`
#
# $\displaystyle\frac{minutes\,in\,game\:+\:minutes\,played\,away\:+\:minutes\,on\,bench}{ minutes\,in\,game} = 1$

proportion_processor = ProportionProcessor(
    variable_names=["minutes_played_home", "minutes_played_away", "minutes_on_bench"],
    reference="minutes_in_game",
    sum_to_one=True,
    decimal_count=0,
)

df.head()

# ### Relative differences
#
# Some variables may have a hierarchy where one variable is always higher than an other. In order to be sure that this hierarchy is preserved in the avatarization, it is recommended to express one variable as the difference of another.
#
# We take `penalty_attempts` and `penalty_goals` as an example where one variable (`penalty_goals`) cannot be greater than the other (`penalty_attempts`).

relative_difference_processor = RelativeDifferenceProcessor(
    target="penalty_goals",
    references=["penalty_attempts"],
)

# ### Relative differences with datetime variables
#
# The relative difference processor can be used to express a date relative to another. To do so, it is required to use the `DatetimeProcessor` that will transform datetime variables into numeric values, by computing the differences between date variables.
#
# As the `DatetimeProcessor` has a post-processing function, the data produced by the avatarization pipeline will contain the datetime variables in their original format (i.e. as datetime values rather than numerical values).

datetime_processor = DatetimeProcessor()

relative_difference_processor_dates = RelativeDifferenceProcessor(
    target="club_signing_date",
    references=["career_start_date"],
)

# ### Computed variables
#
# The data also contains a third variable related to the penalty context: `penalty_misses`. This variable can be computed directly as the difference between `penalty_attempts` and `penalty_goals`.
#
# $\ penalty\:misses = penalty\:attempts - penalty\:goals $
#
# Computed variables should be removed from the data prior to running the avtarization and re-computed after.

df = df.drop(columns=["penalty_misses"])

# ### Run the pipeline

# +
# %%time
dataset = client.pandas_integration.upload_dataframe(df)

result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5)
        ),
        processors=[
            proportion_processor,
            relative_difference_processor,
            datetime_processor,
            relative_difference_processor_dates,
        ],
        df=df,
    ),
    timeout=1000,
)
# -

avatars = result.post_processed_avatars
avatars.head(5)

# +
privacy_metrics = result.privacy_metrics
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

utility_metrics = result.signal_metrics
print("\n*** Utility metrics ***")
for metric in utility_metrics:
    print(metric)
# -

# ### Should these processors really be used ?
#
# Let's try without ...

# +
df2 = pd.read_csv("../fixtures/epl.csv")
df2["career_start_date"] = pd.to_datetime(
    df2["career_start_date"], format="%Y-%m-%d %H:%M:%S"
)
df2["club_signing_date"] = pd.to_datetime(
    df2["club_signing_date"], format="%Y-%m-%d %H:%M:%S"
)

dataset = client.pandas_integration.upload_dataframe(df2)
job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=20, ncp=2, dataset_id=dataset.id)
    )
)
job = client.jobs.get_avatarization_job(id=job.id, timeout=100)
# -

avatars_noprocessing = client.pandas_integration.download_dataframe(
    job.result.avatars_dataset.id, timeout=100
)

avatars_noprocessing.head(5)

# #### Preservation of the proportions
#
# To confirm that proportions are well kept, we can compute the maximum difference between the reference variable (`minutes_in_game`) and the sum of the three proportion variables (`minutes_played_home`, `minutes_played_away` and `minutes_on_bench`). Where it may not be zero when no processor is used, this difference should be zero when using a proportion processor.

np.max(
    abs(
        avatars_noprocessing["minutes_in_game"]
        - (
            avatars_noprocessing["minutes_played_home"]
            + avatars_noprocessing["minutes_played_away"]
            + avatars_noprocessing["minutes_on_bench"]
        )
    )
)

np.max(
    abs(
        avatars["minutes_in_game"]
        - (
            avatars["minutes_played_home"]
            + avatars["minutes_played_away"]
            + avatars["minutes_on_bench"]
        )
    )
)

# #### Preservation of the relative difference

# To confirm that the relative difference is preserved, we can look at the number of players who have more `penalty_goals` than `penalty_attempts`. With the `RelativeDifferenceProcessor` zero players should have more goals than attempts, which is not necessarily the case without processor.
#

print("Avatars with processors")
print(
    "Number of players with penalty attempts > penalty goals: ",
    (sum(avatars["penalty_attempts"] - avatars["penalty_goals"] > 0)),
)
print(
    "Number of players with penalty attempts < penalty goals: ",
    (sum(avatars["penalty_attempts"] - avatars["penalty_goals"] < 0)),
)

print("Avatars without processors")
print(
    "Number of players with penalty attempts > penalty goals: ",
    (
        sum(
            avatars_noprocessing["penalty_attempts"]
            - avatars_noprocessing["penalty_goals"]
            > 0
        )
    ),
)
print(
    "Number of players with penalty attempts < penalty goals: ",
    (
        sum(
            avatars_noprocessing["penalty_attempts"]
            - avatars_noprocessing["penalty_goals"]
            < 0
        )
    ),
)

# ## Post-processors
#
# Post-processors do not transform the data prior to the avatarization but after only. These can be used to fix some variables that could have been altered beyond acceptable.
#
# Care should always be taken when using post-processors because they are likely to **decrease the level of privacy**.
# Using these processors via the pipeline feature, ensure that metrics are computed after application of the post-process step. This also make sure that privacy and utility metrics have taken these processors into consideration.

# ### Expected mean

# `ExpectedMeanProcessor` is used to force values to have similar mean to original data. In our example, we want to preserve the mean of `goals_away` and `goals_home` by the variable `position`.
#
# Care should be taken when using this processor as it only targets enhancement of unimodal utility. This may occur at the expense of multi-modal utility and **privacy**.

expected_mean_processor = ExpectedMeanProcessor(
    target_variables=["goals_away", "goals_home"],
    groupby_variables=["position"],
    same_std=False,
)

# ### Run the pipeline

# +
dataset = client.pandas_integration.upload_dataframe(df)

result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5),
        ),
        processors=[
            proportion_processor,
            relative_difference_processor,
            expected_mean_processor,
        ],
        df=df,
    ),
    timeout=1000,
)
# -

avatars = result.post_processed_avatars
avatars.head(5)

# Looking at the mean of the two variables on which the expected mean processor was applied, we can confirm that the mean for each target category is preserved.
#
# The same statistics computed on avatars that did not get post-processed are more different than the statistics obtained on the original data.

df.groupby(["position"]).mean(numeric_only=True)[["goals_away", "goals_home"]]

avatars.groupby(["position"]).mean(numeric_only=True)[["goals_away", "goals_home"]]

avatars_noprocessing.groupby(["position"]).mean(numeric_only=True)[
    ["goals_away", "goals_home"]
]

# ### Computed variables
#
# To complete the anonymization process, computed variables (that have been removed from the data) should be added back to the avatarized data.
#

avatars["penalty_missed"] = avatars["penalty_attempts"] - avatars["penalty_goals"]
avatars_noprocessing["penalty_missed"] = (
    avatars_noprocessing["penalty_attempts"] - avatars_noprocessing["penalty_goals"]
)

avatars.head()

# ### Perturbation level
#
# The perturbation processor can be used to control how close to the avatarized values, the final values of a variable will be. At the extremes, if using a perturbation level of zero, the avatarized values will not contribute at all to the final values. On the other hand, with a perturbation level of 1, the original values will not contribute. A perturbation level of 0.3 will mean that the final value will be closer to the original values than it is from the anonymized values. By default, the perturbation level is set to 1.

perturbation_processor = PerturbationProcessor(perturbation_level={"age": 1})

# +
result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5),
        ),
        processors=[
            proportion_processor,
            relative_difference_processor,
            expected_mean_processor,
            perturbation_processor,
        ],
        df=df,
    ),
    timeout=1000,
)
avatars_perturbation_1 = result.post_processed_avatars

perturbation_processor = PerturbationProcessor(perturbation_level={"age": 0})
result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5),
        ),
        processors=[
            proportion_processor,
            relative_difference_processor,
            expected_mean_processor,
            perturbation_processor,
        ],
        df=df,
    ),
    timeout=1000,
)
avatars_perturbation_0 = result.post_processed_avatars

perturbation_processor = PerturbationProcessor(perturbation_level={"age": 0.5})
result = client.pipelines.avatarization_pipeline_with_processors(
    AvatarizationPipelineCreate(
        avatarization_job_create=AvatarizationJobCreate(
            parameters=AvatarizationParameters(dataset_id=dataset.id, k=5),
        ),
        processors=[
            proportion_processor,
            relative_difference_processor,
            expected_mean_processor,
            perturbation_processor,
        ],
        df=df,
    ),
    timeout=1000,
)
avatars_perturbation_05 = result.post_processed_avatars
# -

# We observe that as expected, using a perturbation level of 0 on the variable `age`, this variable gets unchanged.

df["age"].value_counts() - avatars_perturbation_0["age"].value_counts()

# The same comment does not hold when using a perturbation level of 0.5 or 1. A count of each modality shows that new modalities were created during avatarization

df["age"].value_counts() - avatars_perturbation_05["age"].value_counts()

df["age"].value_counts() - avatars_perturbation_1["age"].value_counts()

# ### Generate a report after running a pipeline
#
# In this final section, we will illustrate how to produce a report when using the pipeline to perform an avatarization. To do so, we simply need to retrieve the IDs of the avatarization job, privacy metric jobs and utility metric jobs already executed within the pipeline. Those 3 IDs are all in the `AvatarizationPipelineResult` object.

result  # check the content of the AvatarizationPipelineResult object

# +
report = client.reports.create_report(
    ReportCreate(
        avatarization_job_id=result.avatarization_job_id,
        privacy_job_id=result.privacy_job_id,
        signal_job_id=result.signal_job_id,
    ),
    timeout=30,
)
result = client.reports.download_report(id=report.id)

with open("./my_avatarization_report.pdf", "wb") as f:
    f.write(result)
# -

# *In the next tutorial, we will show how to define your own processor to be executed client-side.*
