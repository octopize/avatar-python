# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.16.4
# ---

# ## Comparison tutorial
# This tutorial offer a pipeline in order to evaluate the quality of an avatarization.
#

# +
import numpy as np
import pandas as pd

import seaborn as sns
import missingno as msno
import saiph
import matplotlib.pyplot as plt

from pandas_profiling import ProfileReport

# -

# ## Import data

# +
path_original = "https://raw.githubusercontent.com/octopize/avatar-paper/main/datasets/AIDS/aids_original_data.csv"
df = pd.read_csv(path_original, sep=";").drop(columns=["pidnum"])

path_avatar = "https://raw.githubusercontent.com/octopize/avatar-paper/main/datasets/AIDS/aids_avatarized_base_k20_nf5.csv"
avatar = pd.read_csv(path_avatar)

VALUE = 10
for col in df.columns:
    if len(np.unique(df[col])) < VALUE:
        df[col] = df[col].astype("category")

avatar = avatar.astype(df.dtypes.to_dict())
# -

df

# +
df["type"] = "original"
avatar["type"] = "avatar"

combined = pd.concat([df, avatar], axis=0).reset_index(drop=True)
numerics = ["int", "float"]
col_num = df.select_dtypes(include=numerics).columns
categorical = ["object", "category"]
col_cat = df.select_dtypes(include=categorical).columns


combined.tail()
# -

# ## Univariate comparison
# You can here compare distributions between original and avatar data.
#
# If distributions are not well preserved, you can work with the parameter `columns_weight` in your avatarization.

# Distribution continuous
for col in col_num:
    print(col)
    sns.displot(data=combined, x=col, hue="type", kind="kde")

# Distribution categorical
for col in col_cat:
    print(col)
    plt.figure()
    ax = sns.countplot(
        data=combined,
        x=col,
        hue="type",
    )

# #### Missing data
# You are here comparing missing data between original and avatar data.
#
# If you want to improve the quality of missing data, you can use the parameter `imputation` in your avatarization.

# +
# Missng nan
msno.matrix(avatar)
msno.matrix(df)

print(f"The total number of missing values in avatar : {avatar.isna().values.sum()}")
print(f"The total number of missing values in original : {df.isna().values.sum()}")

avatar_missing_ratio = avatar.isna().values.sum() / avatar.count().count()
df_missing_ratio = df.isna().values.sum() / df.count().count()

print(f"The percentage of missing values in avatar: {avatar_missing_ratio}")
print(f"The percentage of missing values in original: {df_missing_ratio}")
# -

# ## Bivariate comparison
#
# We compare bivariate analysis. We are computing Pearson correlation.
#
# If you want to compare correlations between continuous and categorical variables, you can use Phik correlation (with the `phik` package).
#
# If correlations are not well preserved during the avatarization, you can work with the `column_weight` parameter to add weight to your variables of interest.

# correlation differences
original_corr = df.corr(method="pearson")
avatar_corr = avatar.corr(method="pearson")
corr_diff = abs(original_corr - avatar_corr).round(2)
sns.heatmap(
    corr_diff,
    vmax=1,
    vmin=0,
    square=True,
    linewidths=0.5,
    cbar_kws={"shrink": 0.5},
)

# ## Multivariate comparison
#
# We compare multi-variate structures.
#
# In short, we are checking if the structure of the dataset is preserved.
#
# Datasets should have the same projection on the maximum of the dimensions.
#
# If your projections are not well preserved, you can work with the `ncp` parameter of your avatarization.

# +
# Projection
missing_columns = ["cd496"]  # drop missing data to project
df_proj = df.drop(columns=missing_columns)
avatar_proj = avatar.drop(columns=missing_columns)

NB_IND = 1000  # number of individuals to fit the model.
model = saiph.fit(df_proj.sample(NB_IND).reset_index(drop=True), nf=5)
coord_df = saiph.transform(df_proj, model)
coord_avatar = saiph.transform(avatar_proj, model)
coord_df

# +
from saiph.visualization import plot_projections

plot_projections(model, df_proj)
# -

plot_projections(model, avatar_proj)
