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
# # Quickstart - Avatarization with one table

# %% [markdown]
# ## Connection

# %%
# This is the main file for the Avatar tutorial.
import os
import secrets

from avatars.manager import Manager

# The following are not necessary to run avatar but are used in this tutorial

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("AVATAR_USERNAME", "")
password = os.environ.get("AVATAR_PASSWORD", "")

# %%
manager = Manager(base_url=url)
# Authenticate with the server
manager.authenticate(username, password)

# %% [markdown]
# ## Launching an avatarization

# %%
# The runner is the object that will be used to upload data to the server and run the avatarization
runner = manager.create_runner(set_name=f"test_wbcd_{secrets.token_hex(4)}")
# You can then find the result of the avatarization in the web with the set_name
# Then you need to upload the data to the server
runner.add_table("wbcd", "../fixtures/wbcd.csv")
# Choose the parameters for the avatarization

# %%
runner.set_parameters("wbcd", k=15)
# Run the pipeline with avatarization, privacy and signal metrics and report
runner.run()
# Get the results
results = runner.get_all_results()

# %% [markdown]
# ## Retrieve avatars

# %%
# Print the results
print("Avatar data :")
runner.shuffled("wbcd").head()

# %% [markdown]
# ## Retrieve privacy metrics

# %%
for key, value in runner.privacy_metrics("wbcd")[0].items():
    print(f"{key}: {value}")

# %% [markdown]
# ## Retrieve signal metrics

# %%
for key, value in runner.signal_metrics("wbcd")[0].items():
    print(f"{key}: {value}")

# %% [markdown]
# ## Retrieving the avatarization report

# %%
runner.download_report("my_report.pdf")
