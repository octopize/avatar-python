# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.1
# ---

# %% [markdown]
# # Tutorial 5: Client-side processors

# %% [markdown]
# In this tutorial, we will learn how to prepare the data prior to running an avatarization by using processors on your local machine.
#
# This step is necessary in some cases to handle and preserve data characteristics that are not natively handled by the avatarization or its embedded processors.
#
# We'll also show how custom client-side processors can be defined to integrate domain knowledge into an avatarization.

# %% [markdown]
# ## Principles

# %% [markdown]
# ![pipeline](img/pipeline.png)

# %% [markdown]
# ## Connection

# %%
import os
import secrets

import numpy as np
import pandas as pd

from avatars.manager import Manager
from avatars.models import JobKind
from avatars.processors import (
    ExpectedMeanProcessor,
    GroupModalitiesProcessor,
    PerturbationProcessor,
    ProportionProcessor,
    RelativeDifferenceProcessor,
)

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)
# Verify that we can connect to the API server
manager.get_health()

# %% [markdown]
# ## A helper processor to reduce the number of modalities

# %% [markdown]
# We have seen in the previous tutorial one approach to handle categorical variables with large cardinality. We propose here an alternative way of doing this using a client-side processor.
#
# This processor will group modalities together to ensure the target variable has a requested number of modalities. The least represented modalities will be brought together under a `other` modality. Note that this transformation is irreversible (the original value cannot be infered from `other`).
#
# Because this is an irreversible operation, this transformation of the data should be done outside the pipeline. The transformed data will be used as a basis for comparison when computing utility and privacy metrics.

# %%
df = pd.read_csv("../fixtures/adult_with_cities.csv").head(1000).drop(["native-country"], axis=1)
df.head()

# %% [markdown]
# After loading the data, we decide we wish to reduce the number of modalities for the variable `city` which contains originally over 80 distinct values.

# %%
df["city"].value_counts()

# %%
group_modalities_processor = GroupModalitiesProcessor(
    min_unique=10,  # number of modalities for a variable to be considered for grouping
    global_threshold=25,  # if considered for grouping, number of individuals in modality to preserve it
    new_category="other",
)
df_preprocessed = group_modalities_processor.preprocess(df)

# %% [markdown]
# Once the group modality processor has been applied, we can confirm that the number of modalities for the `city` variables has been reduced

# %%
df_preprocessed["city"].value_counts()

# %%
runner = manager.create_runner(set_name=f"tutorial5{secrets.token_hex(4)}")
runner.add_table(
    "adult",
    df_preprocessed,
)
runner.set_parameters("adult", k=5)
runner.run(jobs_to_run=[JobKind.standard])
runner.get_all_results()

# %%
avatars = runner.shuffled("adult")
avatars.head(3)

# %%
avatars["city"].value_counts()

# %% [markdown]
# We observe that the avatars produced have a reduced number of cities and an extra `other` modality for the `city` variable. Note that the use of a client-side processor made the transformation of the data straightforward.

# %% [markdown]
# ## Modeling inter-variables constraints with processors
# We will now use two processors to enforce inter-variable constraints.
#
# The two processors we will now apply are processors that temporarily transform the data in order to improve the avatarization. This means that they both contain a `preprocess` step and a `postprocess` step, ensuring that the effect of the `preprocess` action can be reversed via the use of the `postprocess` action.
#
# These processors will be used to demonstrate the implementation of the pipeline tool that automates the use of processors, the avatarization and the metric computation in a single command.
#
#

# %%
df = pd.read_csv("../fixtures/epl.csv")

# %% [markdown]
# ### Proportions
# Variables may have relationships in which one or many variables can be represented as a proportion of another. In order to best preserve this type of relationships during avatarization, it is recommended to express such variables as proportions. To do so, the proportion processor can be used.
# In our example, the `ProportionProcessor` can be used, because `minutes_in_game` is the sum of `minutes_played_home`, `minutes_played_away` and `minutes_on_bench`
#
# $\displaystyle\frac{minutes\,in\,game\:+\:minutes\,played\,away\:+\:minutes\,on\,bench}{ minutes\,in\,game} = 1$
#

# %%
proportion_processor = ProportionProcessor(
    variable_names=["minutes_played_home", "minutes_played_away", "minutes_on_bench"],
    reference="minutes_in_game",
    sum_to_one=True,
    decimal_count=0,
)

# %% [markdown]
# ### Relative differences

# %% [markdown]
# Some variables may have a hierarchy where one variable is always higher than an other. In order to be sure that this hierarchy is preserved in the avatarization, it is recommended to express one variable as the difference of another.
# We take `penalty_attempts` and `penalty_goals` as an example where one variable (`penalty_goals`) cannot be greater than the other (`penalty_attempts`).

# %%
relative_difference_processor = RelativeDifferenceProcessor(
    target="penalty_goals",
    references=["penalty_attempts"],
)

# %% [markdown]
# ### Computed variables
# The data also contains a third variable related to the penalty context: `penalty_misses`. This variable can be computed directly as the difference between `penalty_attempts` and `penalty_goals`.
#
# $\ penalty\:misses = penalty\:attempts - penalty\:goals $
#
# Computed variables should be removed from the data prior to running the avtarization and re-computed after.
#

# %%
df = df.drop(columns=["penalty_misses"])

# %%
preprocessed = proportion_processor.preprocess(df)
preprocessed = relative_difference_processor.preprocess(preprocessed)

# %%
runner_with_processor = manager.create_runner(set_name=f"tutorial5{secrets.token_hex(4)}")
runner_with_processor.add_table(
    "game",
    preprocessed,
)
runner_with_processor.set_parameters("game", k=5)
runner_with_processor.run()
runner_with_processor.get_all_results()

# %%
postprocessed = proportion_processor.postprocess(df, runner_with_processor.shuffled("game"))
postprocessed = relative_difference_processor.postprocess(
    df, runner_with_processor.shuffled("game")
)

# %%
privacy_metrics = runner_with_processor.privacy_metrics("game")[0]
print("*** Privacy metrics ***")
for metric in privacy_metrics:
    print(metric)

# %%
signal_metrics = runner_with_processor.signal_metrics("game")[0]
print("*** Signal metrics ***")
for metric in signal_metrics:
    print(metric)

# %% [markdown]
# ### Should these processors really be used ?
# Let's try without ...

# %%
runner_no_processor = manager.create_runner(set_name=f"tutorial5{secrets.token_hex(4)}")
runner_no_processor.add_table(
    "game",
    df,
)
runner_no_processor.set_parameters("game", k=5)
runner_no_processor.run(jobs_to_run=[JobKind.standard])
runner_no_processor.get_all_results()

# %% [markdown]
# #### Preservation of the proportions
# To confirm that proportions are well kept, we can compute the maximum difference between the reference variable (`minutes_in_game`) and the sum of the three proportion variables (`minutes_played_home`, `minutes_played_away` and `minutes_on_bench`). Where it may not be zero when no processor is used, this difference should be zero when using a proportion processor.

# %%
avatars_noprocessing = runner_no_processor.shuffled("game")
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

avatars_processing = runner_with_processor.shuffled("game")
np.max(
    abs(
        avatars_processing["minutes_in_game"]
        - (
            avatars_processing["minutes_played_home"]
            + avatars_processing["minutes_played_away"]
            + avatars_processing["minutes_on_bench"]
        )
    )
)

# %% [markdown]
# #### Preservation of the relative difference
#
# To confirm that the relative difference is preserved, we can look at the number of players who have more `penalty_goals` than `penalty_attempts`. With the `RelativeDifferenceProcessor` zero players should have more goals than attempts, which is not necessarily the case without processor.

# %%
print("Avatars with processors")
print(
    "Number of players with penalty attempts > penalty goals: ",
    (sum(avatars_processing["penalty_attempts"] - avatars_processing["penalty_goals"] > 0)),
)
print(
    "Number of players with penalty attempts < penalty goals: ",
    (sum(avatars_processing["penalty_attempts"] - avatars_processing["penalty_goals"] < 0)),
)

print("Avatars without processors")
print(
    "Number of players with penalty attempts > penalty goals: ",
    (sum(avatars_noprocessing["penalty_attempts"] - avatars_noprocessing["penalty_goals"] > 0)),
)
print(
    "Number of players with penalty attempts < penalty goals: ",
    (sum(avatars_noprocessing["penalty_attempts"] - avatars_noprocessing["penalty_goals"] < 0)),
)

# %% [markdown]
# ## Post-processors
#
# Post-processors do not transform the data prior to the avatarization but after only. These can be used to fix some variables that could have been altered beyond acceptable.
#
# Care should always be taken when using post-processors because they are likely to **decrease the level of privacy**.
# Using these processors via the pipeline feature, ensure that metrics are computed after application of the post-process step. This also make sure that privacy and utility metrics have taken these processors into consideration.
#

# %% [markdown]
# ### Expected mean
#
# `ExpectedMeanProcessor` is used to force values to have similar mean to original data. In our example, we want to preserve the mean of `goals_away` and `goals_home` by the variable `position`.
# Care should be taken when using this processor as it only targets enhancement of unimodal utility. This may occur at the expense of multi-modal utility and **privacy**.
#

# %%
expected_mean_processor = ExpectedMeanProcessor(
    target_variables=["goals_away", "goals_home"],
    groupby_variables=["position"],
    same_std=False,
)
preprocessed = expected_mean_processor.preprocess(df)

# %%
runner = manager.create_runner(set_name=f"tutorial5{secrets.token_hex(4)}")
runner.add_table(
    "game",
    preprocessed,
)
runner.set_parameters("game", k=5)
runner.run(jobs_to_run=[JobKind.standard])
runner.get_all_results()

# %% [markdown]
# Looking at the mean of the two variables on which the expected mean processor was applied, we can confirm that the mean for each target category is preserved.
# The same statistics computed on avatars that did not get post-processed are more different than the statistics obtained on the original data.

# %%
df.groupby(["position"]).mean(numeric_only=True)[["goals_away", "goals_home"]]

# %%
avatars_processing.groupby(["position"]).mean(numeric_only=True)[["goals_away", "goals_home"]]

# %%
avatars_noprocessing.groupby(["position"]).mean(numeric_only=True)[["goals_away", "goals_home"]]

# %% [markdown]
# ### Computed variables
#
# To complete the anonymization process, computed variables (that have been removed from the data) should be added back to the avatarized data.

# %%
avatars_processing["penalty_missed"] = (
    avatars_processing["penalty_attempts"] - avatars_processing["penalty_goals"]
)
avatars_noprocessing["penalty_missed"] = (
    avatars_noprocessing["penalty_attempts"] - avatars_noprocessing["penalty_goals"]
)

# %% [markdown]
# ### Perturbation level
#
# The perturbation processor can be used to control how close to the avatarized values, the final values of a variable will be. At the extremes, if using a perturbation level of zero, the avatarized values will not contribute at all to the final values. On the other hand, with a perturbation level of 1, the original values will not contribute. A perturbation level of 0.3 will mean that the final value will be closer to the original values than it is from the anonymized values. By default, the perturbation level is set to 1.
#

# %%
perturbation_processor = PerturbationProcessor(perturbation_level={"age": 0, "appearances": 1})
preprocessed = perturbation_processor.preprocess(df)

# %%
runner = manager.create_runner(set_name=f"tutorial5{secrets.token_hex(4)}")
runner.add_table(
    "game",
    preprocessed,
)
runner.set_parameters("game", k=5)
runner.run(jobs_to_run=[JobKind.standard])
runner.get_all_results()
avatars_perturbation = runner.shuffled("game")

# %%
postprocessed = perturbation_processor.postprocess(df, runner.shuffled("game"))

# %% [markdown]
# We observe that as expected, using a perturbation level of 0 on the variable `age`, this variable gets unchanged.

# %%
df["age"].value_counts() - postprocessed["age"].value_counts()

# %% [markdown]
# The same comment does not hold when using a perturbation level of 1.
# A count of the number of modalities shows that new modalities were created during avatarization

# %%
df["appearances"].value_counts() - postprocessed["appearances"].value_counts()
