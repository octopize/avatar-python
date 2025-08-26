# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.2
# ---

# %% [markdown]
# # Tutorial 2: Parameterizing an avatarization

# %% [markdown]
# In this tutorial, we will learn how to set key parameters of the avatarization and how they impact privacy and utility.

# %% [markdown]
# ## Connection

# %%
import os

import pandas as pd
from avatar_yaml.models.parameters import (
    ExcludeVariablesMethod,
    ImputeMethod,
)

from avatars.constants import PlotKind
from avatars.manager import Manager
from avatars.models import JobKind

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %% [markdown]
# Run the following cell if your environment does not have all the listed packages already installed.

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)
# Verify that we can connect to the API server
manager.get_health()

# %% [markdown]
# ## Loading data
#
# This tutorial uses the `iris` dataset, allowing us to run several avatarization without delays.

# %%
df = pd.read_csv("../fixtures/iris.csv")

# %%
df.head()

# %%
# The runner is the object that will be used to upload data to the server and run the avatarization
runner_k2 = manager.create_runner("iris_k2")

# Then upload the data, you can either use a pandas dataframe or a file
runner_k2.add_table("iris", df)

# %% [markdown]
# ## Varying k
#
# The parameter *k* can be used to control the tradeoff between privacy and utility. To increase privacy, we recommend increasing the value of k. Because k is the parameter that also impacts the most the utility, it is recommended to alter it gradually.
#
# We demonstrate here the effect of varying *k*.
#

# %%
# Set k
k = 2
runner_k2.set_parameters("iris", k=k)

runner_k2.run()

# Retrieve selected metric
hidden_rate = runner_k2.privacy_metrics("iris")[0]["hidden_rate"]
local_cloaking = runner_k2.privacy_metrics("iris")[0]["local_cloaking"]
hellinger_distance = runner_k2.signal_metrics("iris")[0]["hellinger_mean"]

print(f"With k={k}, the hidden_rate (privacy) is : {hidden_rate}")
print(f"With k={k}, the local_cloaking (privacy) is : {local_cloaking}")
print(f"With k={k}, the hellinger_distance (utility) is : {hellinger_distance}")

# %%
# Create a new runner to run with a different k
runner_k30 = manager.create_runner("iris_k30")
runner_k30.add_table("iris", "../fixtures/iris.csv")

# Set k
k = 30
runner_k30.set_parameters("iris", k=k)

runner_k30.run()

# Retrieve selected metric
hidden_rate = runner_k30.privacy_metrics("iris")[0]["hidden_rate"]
local_cloaking = runner_k30.privacy_metrics("iris")[0]["local_cloaking"]
hellinger_distance = runner_k30.signal_metrics("iris")[0]["hellinger_mean"]

print(f"With k={k}, the hidden_rate (privacy) is : {hidden_rate}")
print(f"With k={k}, the local_cloaking (privacy) is : {local_cloaking}")
print(f"With k={k}, the hellinger_distance (utility) is : {hellinger_distance}")

# download the projections
original_coord_k_30, avatars_coord_k_30 = runner_k30.projections("iris")

# %% [markdown]
# We observe that we are able to increase the level of privacy by simply increasing *k*. But this is at the expense of the utility.

# %% [markdown]
# ## Visualization of originals and avatars

# %% [markdown]
# By looking at originals and avatars in the projected space, we can observe the area covered by avatars and if it covers the same space as the original data.

# %%
# if you are having issues rendering the plot in your notebook, you can use the following line to open the plot in your browser
# runner_k2.render_plot("iris", PlotKind.PROJECTION_3D, open_in_browser=True)
runner_k2.render_plot("iris", PlotKind.PROJECTION_3D)

# %%
runner_k30.render_plot("iris", PlotKind.PROJECTION_3D)

# %% [markdown]
# We observe that the area covered by avatars generated with a low *k* is much closer to the area covered by original data points. We can also see that with a low *k*, some avatars are close to original points that are isolated. This may pose a risk of re-identification. This explains the drop in privacy level when reducing *k*.
#
# Avatars produced with a large *k* are significantly further away from isolated originals and so ensure their privacy. However **care should be taken in setting *k***  with values that are not too high to prevent a drop in utility level. The drop in utility level is represented by the area covered by avatars being much smaller than the ones of originals.

# %% [markdown]
# ## Other parameters

# %% [markdown]
# ### Column weights
#
# Column weights represent the importance of each variable during the projection process. The higher the value for one variable, the more the individuals will be separated regarding this variable.
#
# By default, all variables are given equal weight of 1, but custom weights can be defined to bias the projection towards some specific variables.

# %%
column_weights = {"variety": 3.0}

# %% [markdown]
# ### Number of components
#
# The number of components represents the number of dimensions to consider for the KNN algorithm. With a low value, computation will mostly be based on well-represented variables in the projection.
#
# By default, `ncp` is set to 5, meaning that the 5 dimensions in the projected space that represent the most the variance on the data are used when computing neighbors.

# %%
ncp = 5

# %% [markdown]
# ### Reduction of highly dimensional data
#
# When dealing with variables with a high number of modalities, the number of dimensions created during the projection increase accordingly. This could lead to situations where the number of dimension is too high compared to the number of records.
#
# We developed a parameter to transform categorical data into a restricted number of continuous dimensions embedding categorical variables in vectors.
#
# By default, `use_categorical_reduction` is set to `False`, meaning that categorical variables are left unprocessed. Furthermore, since categorical variables are converted into 20 dimensions by default, it's recommended to enable this parameter if the total number of modalities in the dataset exceeds 20.

# %%
# Turning on categorical reduction will create 20 numeric columns that embed the categorical columns as vectors
# In this particular example it is conterproductive as it dilutes the signal even more (only three modalities in the original dataset)
use_categorical_reduction = True

# %% [markdown]
# ## Categorical variables with large cardinality

# %% [markdown]
# The anonymization of datasets containing categorical variables with large cardinality is not trivial. We recommend to exclude the variable from the avatarization before re-assigning it by individual similarity (`coordinate_similarity`) or by the original row order (`row_order`). Using row order is more likely to preserve identifying information than coordinate similarity. Privacy metrics must be calculated at the end of the process to confirm that the data generated is anonymous.
#
# Metrics are computed after re-assignment of the excluded variables, so a variable that has been excluded is still anonymized as long as the privacy targets are reached.

# %%
exclude_variable_names = ["variety"]
exclude_replacement_strategy = ExcludeVariablesMethod.COORDINATE_SIMILARITY

# %% [markdown]
# ## Missing data
#
# Missing data is common in datasets and is a property that should be modelled.
#
# The Avatar solution can handle variables with missing data without requiring pre-processing. To do so, an additional variable defining whether a value is missing or not will be temporarily added to the data and the missing values will be temporarily imputed. These variables will be part of the anonymization process.
#
# In the presence of missing values, the last step in the avatarization will be to remove temporary variables and add back missing values.
#
# These parameters allow you to choose the method to impute the missing values. `imputation_method` could be : `fast_knn`, `knn` , `mean` , `mode`, `median`. By default we use the `fast_knn` method.

# %%
imputation_method = ImputeMethod.MEAN

# %% [markdown]
# # Running the avatarization

# %% [markdown]
# The avatarization can now be run with different parameters

# %%
runner = manager.create_runner("iris_multi_params")
runner.add_table("iris", "../fixtures/iris.csv")

runner.set_parameters(
    "iris",
    k=k,
    ncp=ncp,
    column_weights=column_weights,
    use_categorical_reduction=use_categorical_reduction,
    # exclude_variable_names=exclude_variable_names,
    # exclude_replacement_strategy=exclude_replacement_strategy,
    # imputation_method=imputation_method,
)

runner.run(jobs_to_run=[JobKind.standard])

# %% [markdown]
# We will now observe the impact of the parameters on the projections. We recommend executing this last part of the tutorial several times with different settings.

# %%
original_coord, avatars_coord = runner.projections("iris")

runner.render_plot("iris", PlotKind.PROJECTION_3D)

# %% [markdown]
# ## Get suggestions for a parameter set
#
# If you don't need to refine the parameter set around your usage, you can use the application's recommendations.
#

# %%
runner = manager.create_runner("iris_automated")

runner.add_table("iris", "../fixtures/iris.csv")
runner.advise_parameters()

# See the automated parameters
runner.print_parameters()

# %%
runner.run()

# %% [markdown]
# You can also update the suggested parameters:

# %%
runner.update_parameters("iris", k=2)
runner.print_parameters()
runner.run()

# %% [markdown]
# ## Compute specific privacy metrics
#
# By configuring the privacy metric parameters, you can simulate specific attack scenarios and adjust the thresholds to suit your use case.

# %% [markdown]
# - **`known_variables`**:
#   List of variables that an attacker is likely to know. This list is used to simulate more realistic attack scenarios, where the attacker only has access to a limited subset of information (typically demographic data). This parameter must be defined alongside the **`target`** and is used to evaluate the **linkability** risk.
#
# - **`target`**:
#   Name of a sensitive variable that an attacker might try to infer. This parameter must be used in conjunction with **`known_variables`** and enables the evaluation of **inference** risk.
#
# - **`quantile_threshold`**:
#   Quantile of the holdout distribution used to define a distance and ratio threshold for computing the closest rate.
#   _Example: If set to 5 (default), any avatar falling below the 5th percentile of the holdout distance distribution is considered at risk._

# %%
runner_privacy = manager.create_runner("iris_multi_params")
runner_privacy.add_table("iris", "../fixtures/iris.csv")

runner_privacy.set_parameters(
    "iris",
    k=10,
    known_variables=["sepal.length", "sepal.width"],
    target="variety",
    quantile_threshold=5,
)

runner_privacy.run(jobs_to_run=[JobKind.standard, JobKind.privacy_metrics])

# Retrieve specific metrics
correlation_protection_rate = runner_privacy.privacy_metrics("iris")[0][
    "correlation_protection_rate"
]
inference_rate = runner_privacy.privacy_metrics("iris")[0]["inference_categorical"]
closest_rate_tunned = runner_privacy.privacy_metrics("iris")[0]["closest_rate"]

print(
    f"the correlation_protection_rate metric measuring linkability is : {correlation_protection_rate}"
)
print(f"the inference_rate metric measuring inference is : {inference_rate}")
print(f"the closest_rate_tunned metric measuring singling out is : {closest_rate_tunned}")

# %% [markdown]
# *In the next tutorial, we will show how to run an avatarization with multiple tables.*
#
