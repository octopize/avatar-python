# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
# ---

# %% [markdown]
# # Tutorial 7: Launching a Privacy Assessment

# %%
import os

import numpy as np
import pandas as pd
from avatar_yaml import DataRecipient

from avatars.constants import JobKind
from avatars.manager import Manager

# %%
manager = Manager(api_key=os.environ.get("AVATAR_API_KEY"))

# %% [markdown]
# ## Loading data

# %% [markdown]
# We recommend loading your file as a pandas dataframe. It enables you to check your data before avatarization and to pre-process it if required.

# %%
# Load the original dataset
df = pd.read_csv("../fixtures/iris.csv")

# %% [markdown]
# # Anonymize your data
# First we are going to create our anonymized datasets, in this tutorial, we will use 3 different methods and compare the results.
# - use avatar to anonymize the data
# - use randomization
# - use the same data as original and anonymized

# %% [markdown]
# ## Anonymize with Avatar

# %%
runner = manager.create_runner("iris_avat")
runner.add_table("iris", data=df)
runner.advise_parameters()
runner.run([JobKind.standard])
df_anonymized = runner.shuffled("iris")

# %% [markdown]
# ## Anonymize with AvatarFastDP
#
# [Learn more about AvatarFastDP](https://docs.octopize.io/docs/principles/method/tabular/differential_privacy#avatarfastdp)

# %%
runner_dp = manager.create_runner("iris_avat_dp")
runner_dp.add_table("iris", data=df)
runner_dp.set_parameters("iris", fast_dp_epsilon=5)
runner_dp.run([JobKind.standard])
df_dp_anonymized = runner_dp.shuffled("iris")

# %% [markdown]
# ## Randomized

# %%
df_randomized = df.copy()
# Shuffle the target variable
df_randomized["variety"] = df_randomized["variety"].sample(frac=1).values
# Add random noise between -1 and 1 to numerical columns
noise = np.random.uniform(-1, 1, size=df_randomized.iloc[:, 0:4].shape)
df_randomized.iloc[:, 0:4] = df_randomized.iloc[:, 0:4] + noise


# %% [markdown]
# # Compute Metrics
#
# ## Understanding the Metrics Comparison
#
# To evaluate and compare our anonymization methods, we'll follow these steps:
#
# 1. **Create a runner with PIA metadata** for each anonymized dataset
#
#    The PIA (Privacy Impact Assessment) context describes your data usage scenario. The platform uses it to automatically calibrate the **privacy targets** against which your metrics are evaluated. Four parameters shape this context:
#
#    | Parameter | API argument | What it describes |
#    |---|---|---|
#    | [**Data Recipient**](https://python.docs.octopize.io/latest/models.html#avatar_yaml.models.avatar_metadata.DataRecipient) | `pia_data_recipient` | Who will receive the anonymized data (`INTERNAL`, `TRUSTED_THIRDPARTY`, `CONTRACTUAL_THIRDPARTY`, `OPENDATA`, `OUTSIDE_EU`) |
#    | [**Data Type**](https://python.docs.octopize.io/latest/models.html#avatar_yaml.models.avatar_metadata.DataType) | `pia_data_type` | Sector of the data (`HEALTH`, `HR`, `FINANCE`, `INSURANCE`, `MOBILITY`, `EDUCATION`) |
#    | [**Data Subject**](https://python.docs.octopize.io/latest/models.html#avatar_yaml.models.avatar_metadata.DataSubject) | `pia_data_subject` | Category of individuals in the dataset (`PATIENTS`, `EMPLOYEES`, `CLIENTS`, `USERS`, `STUDENTS`) |
#    | [**Sensitivity Level**](https://python.docs.octopize.io/latest/models.html#avatar_yaml.models.avatar_metadata.SensitivityLevel) | `pia_sensitivity_level` | How sensitive the personal data is (`VERY_HIGH` → `NEGLIGIBLE`, based on GDPR Art. 4/9) |
#
#    > **What happens when parameters are not set?**
#    > If a parameter is omitted, it defaults to `UNKNOWN` / `UNDEFINED`, privacy targets will be the default ones, which are the stricter.
#    >
#    > In this tutorial we set `pia_data_recipient=DataRecipient.CONTRACTUAL_THIRDPARTY`, meaning the data is shared with a third party under a contractual framework — which results in moderately strict targets reflecting a controlled but external sharing context.
#
#    [Learn more about PIA](https://docs.octopize.io/docs/principles/metrics/reports/impact_assessment)
#
# 2. **Provide pre-anonymized data** using the `avatar_data` parameter
#    - Allows direct assessment of existing anonymized datasets
#
# 3. **Configure privacy assessment**
#    - **known_variables**: Columns most likely known by an attacker (quasi-identifiers like age, gender, location...)
#    - **target**: The sensitive column you want to protect from inference (e.g., salary, health condition)
#
# 4. **Run metrics-only jobs** (privacy_metrics and signal_metrics)
#    - No avatarization is performed, only metrics computation
#
# This workflow efficiently evaluates both **privacy protection** and **data utility** for each anonymization approach.
#


# %%
def compute_metrics(avatar_data):
    runner = manager.create_runner(
        "iris_privacy_assessment", pia_data_recipient=DataRecipient.CONTRACTUAL_THIRDPARTY
    )
    # set avatar_data to allow metrics computation
    runner.add_table("iris", data=df, avatar_data=avatar_data)
    runner.set_parameters(
        "iris",
        known_variables=["sepal.length", "sepal.width", "petal.length", "petal.width"],
        target="variety",
    )
    # run only metrics jobs
    runner.run([JobKind.privacy_metrics, JobKind.signal_metrics])
    return runner


# %%
# Compute metrics for each anonymization method
# We store the runners to access both privacy and signal metrics later
runner_avat_dp = compute_metrics(df_dp_anonymized)
runner_avat = compute_metrics(df_anonymized)
runner_randomized = compute_metrics(df_randomized)
runner_original = compute_metrics(df)

# Extract privacy metrics from each runner
privacy_metrics_avat_dp = runner_avat_dp.privacy_metrics("iris")[0]
privacy_metrics_avat = runner_avat.privacy_metrics("iris")[0]
privacy_metrics_randomized = runner_randomized.privacy_metrics("iris")[0]
privacy_metrics_original = runner_original.privacy_metrics("iris")[0]

# Extract signal metrics from each runner
signal_metrics_avat_dp = runner_avat_dp.signal_metrics("iris")[0]
signal_metrics_avat = runner_avat.signal_metrics("iris")[0]
signal_metrics_randomized = runner_randomized.signal_metrics("iris")[0]
signal_metrics_original = runner_original.signal_metrics("iris")[0]


# %% [markdown]
# # Compare Privacy Metrics Results

# %% [markdown]
# ## What are we comparing?
#
# We're comparing four different approaches :
#
# 1. **Original vs Original**: The baseline measurement comparing the original dataset against itself
#    - This shows the **maximum privacy risk** (worst-case scenario)
#    - When you compare identical data, privacy metrics are at their lowest because all patterns, correlations, and individual records are perfectly preserved
#    - This serves as a reference point to understand the improvement provided by anonymization
#
# 2. **Randomized**: A naive approach using random noise and shuffling
#    - Often destroys utility without providing adequate privacy guarantees
#
# 3. **AVATAR**: Avatar's standard anonymization algorithm
#    - Balances privacy protection with data utility
#
# 4. **AVATAR DP**: Avatar with AvatarFastDP
#    - Applies DP noise during synthesis for additional privacy protection
#    - May have slightly lower utility due to added noise
#
# By comparing all four approaches, we can clearly see the **privacy-utility tradeoff**


# %%
def remove_metadata_keys(metrics_dict):
    return {k: v for k, v in metrics_dict.items() if k not in ["targets", "metadata"]}


# Create a comparison DataFrame for privacy metrics
privacy_comparison = pd.DataFrame(
    {
        "Original": remove_metadata_keys(privacy_metrics_original),
        "Randomized": remove_metadata_keys(privacy_metrics_randomized),
        "AVATAR DP": remove_metadata_keys(privacy_metrics_avat_dp),
        "AVATAR": remove_metadata_keys(privacy_metrics_avat),
        "Targets": privacy_metrics_original["targets"],
    }
)
privacy_comparison

# %% [markdown]
# ## Interpreting Key Privacy Metrics
#
# Looking at the privacy comparison table, let's interpret three metrics:
#
# ### [Hidden Rate](https://docs.octopize.io/docs/principles/metrics/privacy/singling_out/hidden_rate/)
#
# Percentage of individuals whose avatar is not the most similar entry in the dataset (target: ≥ 50%).
# - **Original**: low hidden rate, many records can be singled out due to unique combinations of attributes
# - **Randomized, AVATAR, AVATAR DP**: All meet the target
#
# ### [Linkability Protection Rate](https://docs.octopize.io/docs/principles/metrics/privacy/linkability/linkability_protection_rate/)
#
# Measures protection against linking records across two distinct subsets of variables. This simulates an attacker trying to link records from different databases using overlapping attributes. The metric splits the variables into two groups and evaluates whether an attacker can successfully match records between these groups.
# - **Original**: not all records can be linked, the original data is not perfectly linkable due to natural variability and noise in the data
# - **Randomized, AVATAR, AVATAR DP**: All meet the target
#
# ### [Inference Accuracy Ratio](https://docs.octopize.io/docs/principles/metrics/privacy/inference/unified_attribute_inference/)
#
# Compares inference performance between avatars and original data subsets. Values close to 100% indicate similar inference (no increased risk). Values above 100% mean inference is harder with avatars (better privacy protection). Values below 100% mean avatars make inference easier (increased risk).
# - **Original**: Baseline inference potential
# - **Randomized**: Inference is harder providing good privacy, but this comes at the cost of degrading data utility
# - **AVATAR DP**: Inference is moderately harder, providing privacy protection while maintaining utility
# - **AVATAR**: Close to 100% - Similar inference with utility preservation
#
# All three anonymization methods meet the privacy requirements for our data context.

# %% [markdown]
# # Compare Signal Metrics Results
#
# Signal metrics assess how well the anonymized data preserves the statistical properties and utility of the original data.

# %%
# Create a comparison DataFrame for signal metrics
# Signal metrics measure data utility (how useful the anonymized data remains)

signal_comparison = pd.DataFrame(
    {
        "Original": remove_metadata_keys(signal_metrics_original),
        "Randomized": remove_metadata_keys(signal_metrics_randomized),
        "AVATAR DP": remove_metadata_keys(signal_metrics_avat_dp),
        "AVATAR": remove_metadata_keys(signal_metrics_avat),
        "Targets": signal_metrics_original["targets"],
    }
)
signal_comparison

# %% [markdown]
# ## Interpreting Key Signal Metrics
#
# Looking at the signal comparison table, let's interpret three metrics:
#
# ### [Hellinger Mean](https://docs.octopize.io/docs/principles/metrics/utility/univariate/hellinger_distance/)
#
# Measures how well each individual variable's distribution is preserved (target: > 70). Higher values indicate better preservation of univariate distributions.
# - **Randomized & AVATAR & AVATAR DP**: meet the target
#
# ### [Correlation Difference Ratio](https://docs.octopize.io/docs/principles/metrics/utility/bivariate/correlation_difference_ratio/)
#
# Measures how well correlations between pairs of variables are preserved (target: > 70).
# - **Randomized**: Correlations are significantly degraded
# - **AVATAR & AVATAR DP**: Both meet the target
#
# ### [Multivariate Hellinger Distance Mean](https://docs.octopize.io/docs/principles/metrics/utility/multivariate/multivariate_hellinger_distance/)
#
# Measures how well the joint distribution of all variables is preserved in lower-dimensional projections. Lower values indicate better preservation of multivariate relationships.
# - **Randomized & AVATAR & AVATAR DP**: meet the target
#

# %% [markdown]
#
