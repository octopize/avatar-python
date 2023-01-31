# Tutorial

This Python client communicates with the Avatar platform.

For more information about the Avatar method and process, check out our main docs at https://docs.octopize.io

## Setup

The only remaining step before using the API is setting the endpoint and authenticating. We recommend using environment variables to provide the password.

```python
import os

# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient

# The following are not necessary to run avatar but are used in this tutorial
import pandas as pd
import io

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=os.environ.get("BASE_URL"))
client.authenticate(
    username="username", password=os.environ.get("AVATAR_PASSWORD", "strong_password")
)

# Verify that we can connect to the API server
client.health.get_health()
```

The Python client library is fully type-annotated. This will let you use interface hints from your IDE.

## Quickstart

This is all you need to run and evaluate an avatarization:

```python
from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters
import os

client = ApiClient(base_url=os.environ.get("BASE_URL"))
client.authenticate(username="username", password="strong_password")

dataset = client.datasets.create_dataset(open("fixtures/iris.csv", "r"))

job = client.jobs.create_full_avatarization_job(
    AvatarizationJobCreate(
        parameters=AvatarizationParameters(
            k=20,
            dataset_id=dataset.id,
        ),
    )
)
print(f"got job id: {job.id}")
job = client.jobs.get_avatarization_job(job.id)
print(job.result)
metrics = job.result.privacy_metrics
print(f"got privacy metrics : {metrics}")

# Download the avatars
df = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)
print(df.head())
```

