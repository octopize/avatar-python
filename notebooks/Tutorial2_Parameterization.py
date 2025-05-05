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
# # Tutorial 2: Parameterizing an avatarization

# %% [markdown]
# In this tutorial, we will learn how to set key parameters of the avatarization and how they impact privacy and utility.

# %% [markdown]
# ## Connection

# %%
# This is the main file for the Avatar tutorial.
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from avatars.manager import Manager

# The following are not necessary to run avatar but are used in this tutorial
from avatars.models import JobKind

url = os.environ.get("AVATAR_BASE_API_URL","https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# %% [markdown]
# Run the following cell if your environment does not have all the listed packages already installed.

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)
# Verify that we can connect to the API server
manager.get_health()

# %%
# !pip install openpyxl

# %%
df = pd.read_excel("downloaded/PULWAR_WP1_Simulated_sample.xlsx")

# %%
df["Experience_apprentissage_3_levels"] = df["Experience_apprentissage_3_levels"].apply(
    lambda x: 'None' if pd.isna(x) else x
).astype('category')
column_order=df.columns.tolist()
sexism_to_combine = [
    'confronteavancessex',
    'situationsexisme.SQ001.',
    'situationsexisme.SQ002.',
    'situationsexisme.SQ003.',
    'situationsexisme.SQ004.',
    'situationsexisme.SQ005.'
]

mentor_to_combine = (
    ["presencementor", "statutmentor", "sexmentor"] +
    [f"mentor.{str(i).zfill(2)}" for i in range(1, 38)]
)

# Create the combination columns
df['sexism_combination'] = df[sexism_to_combine].apply(lambda x: '_'.join(x.astype(str)), axis=1)
df['mentor_combination'] = df[mentor_to_combine].apply(
    lambda x: '_'.join('' if pd.isna(val) else str(val) for val in x), axis=1
)

# Save the mapping from combinations to original values
sexism_combination_mapping = df.set_index('sexism_combination')[sexism_to_combine].drop_duplicates().to_dict(orient='index')
mentor_combination_mapping = df.set_index('mentor_combination')[mentor_to_combine].drop_duplicates().to_dict(orient='index')

# drop columns for anonymization
df.drop(columns=sexism_to_combine, inplace=True)
df.drop(columns=mentor_to_combine, inplace=True)

# for all columns that have less than 20 unique values, we will use the "categorical" type
for col in df.columns:
    if df[col].nunique() < 20:
        df[col] = df[col].astype('category')

runner = manager.create_runner("PA_sexism")
runner.add_table("bennoittest", df)
runner.set_parameters("bennoittest", k=5, use_categorical_reduction=True, column_weights={"age": 3, "accesHU": 3})
avatarization_job = runner.run()
results=runner.get_all_results()
avatars = runner.sensitive_unshuffled("bennoittest")
avatars = df.copy()

restored_sexism = avatars['sexism_combination'].map(sexism_combination_mapping).apply(pd.Series)
restored_mentor = avatars['mentor_combination'].map(mentor_combination_mapping).apply(pd.Series)

avatars = avatars.join(restored_sexism)
avatars = avatars.join(restored_mentor)

avatars.drop(columns=['sexism_combination', 'mentor_combination'], inplace=True)
avatars = avatars[column_order]

# %%
runner.download_report("BENOIT/report.pdf")

# %%
runner.shuffled("bennoittest").to_csv("BENOIT/shuffled.csv", index=False)


# %%
runner.sensitive_unshuffled("bennoittest").to_csv("BENOIT/unshuffled.csv", index=False)

# %%
import json

with open("BENOIT/privacy_metrics.json", "w") as file:
    privacy_metrics_json = json.dumps(runner.privacy_metrics("bennoittest"), indent=4)
    file.write(privacy_metrics_json)
print("Privacy metrics saved to privacy_metrics.json")

# %%
with open("BENOIT/signal_metrics.json", "w") as file:
    signal_metrics_json = json.dumps(runner.signal_metrics("bennoittest"), indent=4)
    file.write(signal_metrics_json)
print("Privacy metrics saved to signal_metrics.json")

# %%
avatars = avatars[column_order]

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
runner = manager.create_runner("iris_k2")

# Then upload the data, you can either use a pandas dataframe or a file
runner.add_table("iris", df)

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
runner.set_parameters("iris", k=k)

runner.run()

# Retrieve selected metric
hidden_rate = runner.privacy_metrics("iris")["hidden_rate"]
local_cloaking = runner.privacy_metrics("iris")["local_cloaking"]
hellinger_distance = runner.signal_metrics("iris")["hellinger_mean"]

print(f"With k={k}, the hidden_rate (privacy) is : {hidden_rate}")
print(f"With k={k}, the local_cloaking (privacy) is : {local_cloaking}")
print(f"With k={k}, the hellinger_distance (utility) is : {hellinger_distance}")

original_coord_k_2, avatars_coord_k_2  = runner.projections("iris")

# %%
# Create a new runner to run with a different k
runner = manager.create_runner("iris_k30")
runner.add_table("iris", "../fixtures/iris.csv")

# Set k
k = 30
runner.set_parameters("iris", k=k)

runner.run()

# Retrieve selected metric
hidden_rate = runner.privacy_metrics("iris")["hidden_rate"]
local_cloaking = runner.privacy_metrics("iris")["local_cloaking"]
hellinger_distance = runner.signal_metrics("iris")["hellinger_mean"]

print(f"With k={k}, the hidden_rate (privacy) is : {hidden_rate}")
print(f"With k={k}, the local_cloaking (privacy) is : {local_cloaking}")
print(f"With k={k}, the hellinger_distance (utility) is : {hellinger_distance}")

original_coord_k_30, avatars_coord_k_30  = runner.projections("iris")


# %% [markdown]
# We observe that we are able to increase the level of privacy by simply increasing *k*. But this is at the expense of the utility.

# %% [markdown]
# ## Visualization of originals and avatars

# %% [markdown]
# By looking at originals and avatars in the projected space, we can observe the area covered by avatars and if it covers the same space as the original data.

# %%
def plot_coordinates(original_coord, avatars_coord, k: int |  None = None):
    projections_records = np.array(original_coord)[
        :, 0:2
    ]  # First 2 dimensions of projected records
    projections_avatars = np.array(avatars_coord)[
        :, 0:2
    ]  # First 2 dimensions of projected records

    fig, ax = plt.subplots(1, 1)
    sns.scatterplot(
        ax=ax,
        x=projections_records[:, 0],
        y=projections_records[:, 1],
        alpha=0.6,
        color="dimgrey",
        label="Original",
    )

    sns.scatterplot(
        ax=ax,
        x=projections_avatars[:, 0],
        y=projections_avatars[:, 1],
        alpha=0.6,
        color="#3BD6B0",
        label="Avatars",
    )

    ax.set_title(f"Projection of originals and avatars {k=}")
plot_coordinates(original_coord_k_2, avatars_coord_k_2, 2)

# %%
plot_coordinates(original_coord_k_30, avatars_coord_k_30, 30)

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
column_weights = {"variety": 3}

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
exclude_variable_names=["variety"]
exclude_replacement_strategy='coordinate_similarity'

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
imputation_method="mean"

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
runner.get_all_results()

# %% [markdown]
# We will now observe the impact of the parameters on the projections. We recommend executing this last part of the tutorial several times with different settings.

# %%
original_coord, avatars_coord = runner.projections("iris")

plot_coordinates(original_coord, avatars_coord, k)

# %% [markdown]
# *In the next tutorial, we will show how to run an avatarization with multiple tables.*
#
