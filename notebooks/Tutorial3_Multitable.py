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
# # Tutorial 3: Multitable
#

# %% [markdown]
#   In this tutorial, we will execute the avatarization of a multi-table dataset. If you want to know more about how the anonymization is performed, you can read [this page](https://docs.octopize.io/docs/principles/method/multi_table/).
#

# %% [markdown]
# ### Setup

# %%
# %matplotlib inline
import os
import secrets

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from avatar_yaml.models.schema import LinkMethod

from avatars.manager import Manager
from avatars.models import JobKind

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)

# %% [markdown]
# ## Loading data

# %% [markdown]
# In this tutorial, we will avatarise data that contains a patient table, a doctor table and a visit table
# - There are 130 patients having at least 1 visit
# - There are 50 doctors, they all did at least one visit
# - There are 300 visits
#
# Note:
# - Each table has a primary key with only unique values
# - Each child table refers to a parent table using a foreign key

# %% [markdown]
# <img src="img/multitable.png" style="height:500px" />

# %%
doctor = pd.read_csv("../fixtures/doctor.csv", sep=",")
patient = pd.read_csv("../fixtures/patient.csv", sep=",")
visit = pd.read_csv("../fixtures/visit.csv", sep=",")

# %%
patient.head()

# %%
doctor.head()

# %%
visit.head()

# %% [markdown]
# ## Upload data
# First we need to upload each table in the database.
# Each id column name MUST be specified in the `primary_key` and `foreign_keys` parameter
#
# Note:
# - Any table need variable that is unique for each rows (primary key)
# - When there is a link between 2 tables, we need to specify the links between them.
# - A parent table has at least a primary key. In our case patient and doctor are parent table.
# - A child table must have a primary key and as many foreign keys as it has parent tables. In our case visit is a child table.
# - An individual level table is a dataframe where each row refers to a UNIQUE physical individual. Privacy metrics assess the re-identification risk of these individuals.
# - A table with no child must be at individual level.

# %%
# First initialize the runner
runner = manager.create_runner(set_name=f"tutorial_multitable{secrets.token_hex(4)}")

runner.add_table(
    "patient",
    patient,
    primary_key="p_id",
    individual_level=True,
)

runner.add_table(
    "doctor",
    doctor,
    primary_key="d_id",
    individual_level=True,
)


runner.add_table(
    "visit",
    visit,
    primary_key="visit_id",
    foreign_keys=["patient_id", "doctor_id"],
)

# %% [markdown]
# ## Parameters setup

# %% [markdown]
# Before proceeding to anonymization, you need to specify the links between each table, as well as the anonymization parameters for each table.
#
# We can choose the method to link a child to its parent table after anonymization :
# - *LINEAR_SUM_ASSIGNMENT*: Assign using the linear sum assignment algorithm.
#     This method is a **good privacy and** utility trade-off. The algorithm consumes lots of resources.
#
# - *MINIMUM_DISTANCE_ASSIGNMENT*: Assign using the minimum distance assignment algorithm.
#     This method assigns the closest child to the parent. It is an acceptable privacy and utility
#     trade-off.
#     This algorithm consumes **less resources** than the linear sum assignment.
#
# - *SENSITIVE_ORIGINAL_ORDER_ASSIGNMENT*: Assign the child to the parent using the original order.
#     **WARNING!!! This method is a HIGH PRIVACY BREACH as it keeps the original order to assign
#     the child to the parent.**
#     This method isn't recommended for small datasets for privacy reasons but consumes **less resources** than the other
#     methods.
#
# Note:
# - A link is a relation between 1 parent table and 1 child table

# %%
runner.add_link(
    parent_table_name="patient",
    child_table_name="visit",
    parent_field="p_id",
    child_field="patient_id",
    method=LinkMethod.LINEAR_SUM_ASSIGNMENT,
)
# Linear sum assignment consumes lots of ressource. Change the method if you have a large dataset.

runner.add_link(
    parent_table_name="doctor",
    child_table_name="visit",
    parent_field="d_id",
    child_field="doctor_id",
    method=LinkMethod.LINEAR_SUM_ASSIGNMENT,
)

# %%
runner.advise_parameters()
runner.update_parameters(
    "patient",
    known_variables=[
        "gender",
        "age",
    ],
)

runner.print_parameters()

# %% [markdown]
# ## Anonymization

# %%
runner.run()

# %%
# Get back avatar tables from the results
# Patient
patient_avatar = runner.shuffled("patient")
# Doctor
doctor_avatar = runner.shuffled("doctor")
# Visit
visit_avatar = runner.shuffled("visit")

# %%
patient_avatar.head()

# %%
doctor_avatar.head()

# %%
visit_avatar.head()

# %% [markdown]
# ## Privacy metric computation
# Similarly to multitable avatarization, privacy metrics calculation requires the specification of one set of parameter per table.

# %%
# verify that the job is finished
runner.get_status(JobKind.privacy_metrics)

# %% [markdown]
# ## Privacy metric results
# The privacy metrics results are computed on multiple tables to verify as many attack scenario as possible.
#
# All types of multi table privacy scenario are further described [here](https://docs.octopize.io/docs/understanding/multi_table/).

# %% [markdown]
# <img src="img/multitable_privacy.png" style="height:500px" />

# %% [markdown]
# ## RAW results

# %%
print("*** Privacy metrics on the patient table***")
for method in runner.privacy_metrics("patient"):
    print(f"Computation type : {method['metadata']['computation_type']}")
    print(f"   Hidden rate : {method['hidden_rate']}")

# %% [markdown]
# Key understandings:
# - **Standalone**: Indicates that the patient table, when considered independently, is protected.
# - **To_top_enriched**: Suggests that combining information from the visit table reduces the level of protection.

# %%
print("*** Privacy metrics on the doctor table***")
for method in runner.privacy_metrics("doctor"):
    print(f"Computation type : {method['metadata']['computation_type']}")
    print(f"   Hidden rate : {method['hidden_rate']}")

# %% [markdown]
# Key understandings:
# - **Standalone**: Indicates that the doctor table, when considered independently, is protected.
# - **To_top_enriched**: Suggests that combining information from the visit table reduces the level of protection.

# %%
print("*** Privacy metrics on the visit table***")
for method in runner.privacy_metrics("visit"):
    print(
        f"Computation type : {method['metadata']['computation_type']} with table {method['metadata']['reference']}"
    )
    print(f"   Hidden rate : {method['hidden_rate']}")

# %% [markdown]
# Key insights:
# As the visit table is not at the individual level, metrics are calculated using individual ID variables from parent tables (patient, doctor).
#
# - **to_bottom_id_propagated with table doctor**: looking at the hidden_rate, the visit table does not expose information about doctors.
# - **full_enriched with table doctor**: Combining the visit table with patient-broadcasted data does not expose doctor information.
#
# - **to_bottom_id_propagated with table patient**: looking at the hidden_rate, the visit table does not expose information about patient.
# - **full_enriched with table patient**: Combining the visit table with doctor-broadcasted data does not expose patient information.
#

# %% [markdown]
# # Utility evaluation

# %% [markdown]
# ## Compute signal metrics on multitable context

# %%
# Check the status of the job
runner.get_status(JobKind.signal_metrics)

# %%
print("*** Signal metrics on the patient table***")
for method in runner.signal_metrics("patient"):
    print(f"Computation type : {method['metadata']['computation_type']}")
    print(f"   Hellinger mean : {method['hellinger_mean']}")

# %% [markdown]
# Key insights:
#
# - **Standalone**:  The avatarized patient table preserves the original distribution effectively.
# - **To_top_enriched**: These metrics indicate if the link between the patient and visit tables is well preserved.

# %%
print("*** Signal metrics on the doctor table***")
for method in runner.signal_metrics("doctor"):
    print(f"Computation type : {method['metadata']['computation_type']}")
    print(f"   Hellinger mean : {method['hellinger_mean']}")

# %% [markdown]
# Key insights:
#
# - **Standalone**: The avatarization of the doctor table preserves the original distribution well.
# - **To_top_enriched**: The link between the doctor and visit table is preserved.

# %%
print("*** Signal metrics on the visit table***")
for method in runner.signal_metrics("visit"):
    print(
        f"Computation type : {method['metadata']['computation_type']} with table {method['metadata']['reference']}"
    )
    if method["metadata"]["computation_type"] == "standalone":
        print(f"   Hellinger mean : {method['hellinger_mean']}")
    print(f"   Correlation difference ratio : {method['correlation_difference_ratio']}")

# %% [markdown]
# Key insights:
#
# - **Standalone**: The avatarization of the visit table preserves the original distribution well.
# - **to_bottom_information_propagated with table doctor**: The correlation between the doctor and visit table is well preserved.
# - **to_bottom_information_propagated with table patient**: The correlation between the patient and visit table is well preserved.

# %% [markdown]
# ## Download Report

# %%
runner.download_report("multitable-report.pdf")

# %% [markdown]
# ## Multivariate comparison
#

# %% [markdown]
# You can see how the avatarization affect the link between original and avatar data.
# You can try with different `LinkMethod` and observe how it impacts the link between tables

# %% [markdown]
# ### Visit x Patient

# %%
AVATAR_COLOR = "#3BD6B0"
ORIGINAL_COLOR = "dimgrey"
map_color = {"original": ORIGINAL_COLOR, "avatar": AVATAR_COLOR}
day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

doctor_avatar_renamed = doctor_avatar.rename(columns={"age": "age_doctor"})
visit_avatar_flat = visit_avatar.join(doctor_avatar_renamed.set_index("d_id"), on="doctor_id")
visit_avatar_flat = visit_avatar_flat.join(patient_avatar.set_index("p_id"), on="patient_id")


doctor_renamed = doctor.rename(columns={"age": "age_doctor"})
visit_flat = visit.join(doctor_renamed.set_index("d_id"), on="doctor_id")
visit_flat = visit_flat.join(patient.set_index("p_id"), on="patient_id")

# %%
visit_flat["day_visit"] = pd.Categorical(
    visit_flat["day_visit"], categories=day_order, ordered=True
)
visit_flat = visit_flat.sort_values("day_visit")
visit_avatar_flat["day_visit"] = pd.Categorical(
    visit_avatar_flat["day_visit"], categories=day_order, ordered=True
)
visit_avatar_flat = visit_avatar_flat.sort_values("day_visit")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sns.countplot(
    data=visit_flat,
    x="day_visit",
    hue="gender",
    ax=axes[0],
    palette=[ORIGINAL_COLOR, "lightgrey"],
)
sns.countplot(
    data=visit_avatar_flat,
    x="day_visit",
    hue="gender",
    ax=axes[1],
    palette=[AVATAR_COLOR, "#9fe9d7"],
)
axes[0].set_title("Original")
axes[1].set_title("Avatar")

# %% [markdown]
# ### Visit x Doctor

# %%
visit_flat["day_visit"] = pd.Categorical(
    visit_flat["day_visit"], categories=day_order, ordered=True
)
visit_flat = visit_flat.sort_values(["day_visit", "exam"])
visit_avatar_flat["day_visit"] = pd.Categorical(
    visit_avatar_flat["day_visit"], categories=day_order, ordered=True
)
visit_avatar_flat = visit_avatar_flat.sort_values(["day_visit", "exam"])
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sns.boxplot(
    data=visit_flat,
    x="age_doctor",
    y="day_visit",
    ax=axes[0],
    color=ORIGINAL_COLOR,
)
sns.boxplot(
    data=visit_avatar_flat,
    x="age_doctor",
    y="day_visit",
    ax=axes[1],
    color=AVATAR_COLOR,
)
axes[0].set_xlim(30, 70)
axes[1].set_xlim(30, 70)
axes[0].set_title("Original")
axes[1].set_title("Avatar")

# %%
visit_avatar_flat = visit_avatar_flat.sort_values("exam")
visit_flat = visit_flat.sort_values("exam")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sns.countplot(
    data=visit_flat,
    x="exam",
    hue="job",
    ax=axes[0],
    palette=[ORIGINAL_COLOR, "lightgrey"],
)
sns.countplot(
    data=visit_avatar_flat,
    x="exam",
    hue="job",
    ax=axes[1],
    palette=[AVATAR_COLOR, "#9fe9d7"],
)
axes[0].set_title("Original")
axes[1].set_title("Avatar")

# %% [markdown]
# ### Patient x Doctor

# %%
sns.kdeplot(data=visit_flat, x="age", y="age_doctor", fill=True, color=ORIGINAL_COLOR, alpha=0.8)
sns.kdeplot(
    data=visit_avatar_flat,
    x="age",
    y="age_doctor",
    fill=True,
    color=AVATAR_COLOR,
    alpha=0.8,
)

# %%
