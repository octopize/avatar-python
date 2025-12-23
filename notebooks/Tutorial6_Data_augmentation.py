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
# # Tutorial 6: Data Augmentation
#
# In this tutorial, you'll learn how to use Avatar's data augmentation capabilities to address class imbalance and increase dataset size while preserving statistical properties and privacy.

# %% [markdown]
# ## Connection

# %%
import os

import pandas as pd
from avatar_yaml.models.parameters import AugmentationStrategy

from avatars.constants import ColumnType, PlotKind
from avatars.manager import Manager
from avatars.models import JobKind

base_url = os.environ.get("AVATAR_BASE_URL", "http://localhost:8080/api")
username = os.environ.get("AVATAR_USERNAME", "user_integration")
password = os.environ.get("AVATAR_PASSWORD", "password_integration")

# %%
manager = Manager()  # or manager = Manager(base_url=https://your-server.com)
# Authenticate with the server
manager.authenticate(username, password)

# %% [markdown]
# ## What is Data Augmentation with Avatar?
#
# Data augmentation uses avatarization to generate synthetic individuals that share the same statistical properties as your original dataset. This is particularly useful when:
#
# - **Your dataset has class imbalance**: Some categories have too few samples for effective model training
# - **You need more data**: Your dataset is too small and you want to increase its size while maintaining privacy
#
# Avatar offers two main augmentation strategies:
#
# 1. **Class Balancing**: Increase the number of individuals in underrepresented classes of a categorical variable
# 2. **Multiplier Augmentation**: Apply a multiplication factor to increase the entire dataset size uniformly

# %% [markdown]
# ## Example 1: Balancing Minority Classes
#
# Let's use the Wisconsin Breast Cancer Diagnostic (WBCD) dataset, which has an imbalanced class distribution. We'll balance the second minority class to improve model training.
#
# ### Step 1: Load and Explore the Data

# %%
df = pd.read_csv("../fixtures/wbcd.csv")

# Check the class distribution
print("Original class distribution:")
print(df["Class"].value_counts())
print(f"\nTotal samples: {len(df)}")

# %%
df.sample(5)

# %% [markdown]
# ### Step 2: Configure the Augmentation
#
# We'll use the `minority` strategy, which increases the minority class to match the majority class size.

# %%
# Create a runner for this augmentation job
runner = manager.create_runner("data_augmentation_minority")

dtypes = {}
for col in df.columns:
    dtypes[col] = ColumnType.CATEGORY
# Upload the data and specify thats all variables are categorical column
runner.add_table("wbcd", df, types=dtypes)

# Configure augmentation parameters
runner.set_parameters(
    table_name="wbcd",
    k=5,
    data_augmentation_strategy=AugmentationStrategy.minority,  # Balance minority class
    data_augmentation_target_column="Class",  # Column to balance
)

# %% [markdown]
# ### Step 3: Run the Augmentation

# %%
# Run the avatarization with augmentation
runner.run(jobs_to_run=[JobKind.standard])

# %% [markdown]
# ### Step 4: Retrieve and Verify the Augmented Data

# %%
# Retrieve the augmented dataset
augmented_data = runner.shuffled("wbcd")

# Check the new class distribution
print("Augmented class distribution:")
print(augmented_data["Class"].value_counts())
print(f"\nTotal samples: {len(augmented_data)}")
print(f"Original samples: {len(df)}")
print(f"New samples generated: {len(augmented_data) - len(df)}")

# %% [markdown]
# #### Understanding the Results
#
# Looking at the output above, we can observe:
#
# 1. **Class Balance Achieved**: The minority class (4) has been augmented  to match the majority class
# 2. **Synthetic Records Generated**: Avatar created new synthetic records to balance the dataset
# 3. **Near-Perfect Balance**: The classes are now balanced with approximately equal counts
#
# **Why not exactly the same count?**
#
# The slight variation occurs because:
# - Avatarization is inherently a **stochastic process** that introduces controlled randomness
# - This randomness is a key feature that ensures **privacy preservation** -
# - The difference is minimal (less than 1%) and doesn't affect the practical benefit of class balancing

# %% [markdown]
# ### Step 5: Visualize the Results
#
# You can generate plots to visualize the distribution and verify the augmentation quality.

# %%
# View the distribution plot showing the balanced classes
runner.render_plot("wbcd", PlotKind.DISTRIBUTION, open_in_browser=False)

# %%
# Visualize the class separation in 2D space
runner.render_plot("wbcd", PlotKind.CLASS_PROJECTION_2D, open_in_browser=False)

# %% [markdown]
# ## Example 2: Multiplier Augmentation
#
# Multiplier augmentation increases your entire dataset by a specified factor, regardless of class distribution. This is useful when you simply need more data for training.
#
# ### Use cases:
# - Your dataset is too small for effective model training
# - You want to test model performance with larger datasets
# - You need to generate synthetic data while preserving privacy

# %%
runner_augmented_factorial = manager.create_runner("data_augmentation_factorial")

runner_augmented_factorial.add_table("wbcd", df, types=dtypes)

# Configure to balance all classes to the majority
runner_augmented_factorial.set_parameters(
    table_name="wbcd",
    k=5,
    data_augmentation_strategy=3,  # Multiplier augmentation
)

# Run the augmentation
runner_augmented_factorial.run(jobs_to_run=[JobKind.standard])

# Retrieve and verify the augmented dataset
shuffle = runner_augmented_factorial.shuffled("wbcd")

print(f"Original dataset size: {len(df)}")
print(f"Augmented dataset size: {len(shuffle)}")
print(f"Multiplication factor: {len(shuffle) / len(df):.2f} x")

# Verify class proportions are preserved
print("\nOriginal class proportions:")
print(df["Class"].value_counts(normalize=True))
print("\nAugmented class proportions:")
print(shuffle["Class"].value_counts(normalize=True))

# %% [markdown]
# #### Understanding Multiplier Augmentation Results
#
# The output demonstrates how multiplier augmentation maintains dataset characteristics while scaling size:
#
# 1. **Exact Multiplication**: The dataset grew from 683 to 2,049 samples, achieving precisely the 3.00x factor requested
# 2. **Preserved Class Proportions**: The class distribution remained nearly identical:
# 3. **Statistical Consistency**: The tiny variations (0.1-0.2%) confirm that anonymization preserves the original data's statistical properties while generating synthetic records
#
# Unlike class balancing strategies, multiplier augmentation **maintains existing imbalances** - it's useful when you need more data but want to preserve the natural class distribution of your dataset.

# %% [markdown]
# ## Summary of Augmentation Strategies
#
# | Strategy | Purpose | When to Use | Parameter |
# |----------|---------|-------------|-----------|
# | `minority` | Balance minority class to match majority | Binary classification with imbalance |  `data_augmentation_strategy` &  `data_augmentation_target_column` |
# | `not_majority` | Balance all classes to match the largest | Multi-class with multiple underrepresented classes |  `data_augmentation_strategy` &  `data_augmentation_target_column` |
# | `multiplier` | Multiply entire dataset size | Need more data while preserving proportions | `data_augmentation_strategy` |
# | `custom proportion` | Apply custom proportion to each class | Custom project | `data_augmentation_strategy` & `data_augmentation_target_column` |
#
# ### Key Points:
# - All strategies maintain the statistical properties of your original data
# - Augmented data is synthetic and privacy-preserving
# - You can adjust the `k` parameter to control privacy (higher k = more privacy, less utility)
# - Verify the augmented data distribution matches your expectations

# %% [markdown]
# ## Data Augmentation with Full Pipeline
#
# You can also generate privacy metrics, signal metrics, and reports alongside data augmentation. The workflow remains the same as in previous tutorials.

# %%
runner_full_process = manager.create_runner("data_augmentation_full_process")

runner_full_process.add_table("wbcd", df, types=dtypes)

# Configure to balance all classes to the majority
runner_full_process.set_parameters(
    table_name="wbcd",
    k=5,
    data_augmentation_strategy=AugmentationStrategy.not_majority,
    data_augmentation_target_column="Mitoses",
)

# Run the augmentation
runner_full_process.run()  # Avatarization then privacy metrics, signal metrics, and report

# Retrieve and verify the augmented dataset
shuffled = runner_full_process.shuffled("wbcd")

# %% [markdown]
# We compute metrics on multiple attack scenarios. Here is a table summary of the computation types:
#
#
# | Metric Type                    | Original Data            | Avatar Data                | Privacy Answer                                                                                        |
# | ------------------------------ | ------------------------ | -------------------------- | ----------------------------------------------------------------------------------------------------- |
# | **STANDALONE**                 | All originals            | All avatars                | Can any avatar record compromise the privacy of its corresponding original record?                    |
# | **BARYCENTERED**               | All originals            | Barycenters                | Can the aggregation of all avatars for an original record compromise its privacy?                     |
# | **CLASS_BALANCING_BARYCENTER** | Only augmented originals | Only augmented barycenters | Does the augmentation process increase privacy risk for originals that were augmented multiple times? |
#

# %%
# Retrieve privacy metrics
print("*** Privacy metrics ***")
for method in runner_full_process.privacy_metrics("wbcd"):
    print(f"Computation type: {method['metadata']['computation_type']}")
    print(f"  Hidden rate: {method['hidden_rate']}")
    print(f"  Distance to closest: {method['distance_to_closest']}")

# %%
runner_full_process.download_report("wbcd_report.pdf")  # report with specific augmentation metrics
