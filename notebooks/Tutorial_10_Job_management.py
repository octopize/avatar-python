# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.16.4
# ---

# # Tutorial 10: Job management

# In this tutorial, we show how to manage the jobs that a user creates. Poor job management can lead to the creation of long queues of jobs on the server side, preventing new jobs to start.
#
# It is particularly important when executing large jobs or trying out many parameters. The execution of some may take longer than expected and a user may want to stop them to enable the start of other ones.
#
# Here are a few situations that can be unlocked by "cleaning" the job queue:
# - None of my submitted jobs get started
# - I have launched a job with the wrong parameters and I realize it will take a long time
# - I urgently need to run a job but larger jobs are already in the queue.
# - etc...

# # Connection

# +
import os

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters
from avatars.models import ReportCreate
from avatars.models import JobStatus

import pandas as pd
import numpy as np
import io

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

# Verify that we can connect to the API server
client.health.get_health()

# Verify that the client is compatible.
client.compatibility.is_client_compatible()
# -

# # Job creation
#
# Let us create one job for demonstration purposes. This step may not be necessary if you have already created jobs.

# +
df = pd.read_csv("../fixtures/iris.csv")

dataset = client.pandas_integration.upload_dataframe(df)

avatarization_job = client.jobs.create_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(k=20, dataset_id=dataset.id),
    )
)
print(avatarization_job.id)
# -

# ## View jobs created

# #### Get all jobs (ordered by creation date descending)

jobs = client.jobs.find_all_jobs_by_user()
jobs

# #### Number of jobs created by the logged user

len(jobs)

# #### Get last created job

jobs[0]

# #### Get all pending jobs

pending_jobs = [job for job in jobs if job.status == JobStatus.pending]
print(f"There are {len(pending_jobs)} pending jobs.")
pending_jobs

# #### Get all failed jobs

failed_jobs = [job for job in jobs if job.status == JobStatus.failure]
print(f"There are {len(failed_jobs)} failed jobs.")
failed_jobs

# You may be interested in the reason(s) why those jobs have failed. For this, the error message can be accessed.

error_messages = [job.error_message for job in jobs if job.status == JobStatus.failure]
for error in error_messages:
    print(error)

# #### Get all killed jobs

killed_jobs = [job for job in jobs if job.status == JobStatus.killed]
print(f"There are {len(killed_jobs)} pending jobs.")
killed_jobs

# #### Get all started jobs

started_jobs = [job for job in jobs if job.status == JobStatus.started]
print(f"There are {len(started_jobs)} pending jobs.")
started_jobs

# ## Cancel jobs
#
# Jobs submitted by users are queued before being executed. Several jobs can be executed in parallel but there is  a limit on how many. For this reason, managing created jobs is essential to enable the successful completion of additional jobs.

# +
# get last created job
last_job_id = jobs[0].id
print(last_job_id)

# cancel it
last_job = client.jobs.cancel_job(last_job_id)

# the status of that job is now `killed`.
last_job.status
# -

# ## View datasets
#
# It may also be useful to manage datasets to avoid unnecessary upload of the same data for example. The `find_all_datasets_by_user()` function will give you all datasets for which you have access with some basic statistics such as number of lines and dimensions.

# #### Get all datasets of the user

client.datasets.find_all_datasets_by_user()

len(client.datasets.find_all_datasets_by_user())
