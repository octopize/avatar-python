# Tutorial

This Python client communicates with the avatarization engine. For more information about the concepts and avatarization, check out our main docs at https://docs.octopize.io.

## Installation

Install the package by pointing to the .whl file (replace path below).

```bash
pip install "~/Downloads/avatars-0.X.X-py3-none-any.whl"
# or, if you're using poetry (recommended)
poetry add "~/Downloads/avatars-0.X.X-py3-none-any.whl"
```

to install the project dependencies.

## Loading the library

Once installed, load the library:

```python
# This is the client that you'll be using for all of your requests
from avatars.client import ApiClient

## The following are not necessary to run avatar but are needed for this tutorial
import pandas as pd
import io
```

## Preliminary steps

The only remaining step before using the API is setting the API endpoint and authenticating:

```python
import os

# Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
client = ApiClient(base_url=os.environ.get("BASE_URL"))
client.authenticate(username="username", password="strong_password")

# Let's verify that we can connect to the API server
client.health.get_health()
```

## Quickstart

This is all you need to run and evaluate an avatarization:

```python
from avatars.client import ApiClient
from avatars.models import JobCreate, AvatarizationParameters
import os

client = ApiClient(base_url=os.environ.get("BASE_URL"))
client.authenticate(username="username", password="strong_password")

dataset = client.datasets.create_dataset(open("fixtures/iris.csv", "r"))

job = client.jobs.create_job(
    JobCreate(
        dataset_id=dataset.id,
        parameters=AvatarizationParameters(k=20),
    )
)
print(f"got job id: {job.id}")

job = client.jobs.get_job(job.id)
print(job.result)
metrics = job.result.privacy_metrics
print(f"got privacy metrics : {metrics}")

# Download the avatars
dataset = client.datasets.download_dataset(job.result.avatars_dataset.id)
```

## Avatarization step by step

### Manipulate datasets

You can pass the data to `create_dataset()` directly as a file handle.
The file can be opened as bytes (`"rb"`) or as string `"r"` with `utf-8` encoding.

#### Using CSV files

```python
filename = "fixtures/iris.csv"

# Using a context manager
with open(filename, "r") as f:
    dataset = client.datasets.create_dataset(request=f)

# Inline
dataset = client.datasets.create_dataset(request=open(filename, "r"))
dataset = client.datasets.create_dataset(request=open(filename, "rb"))
```

#### With `pandas` dataframes

If you are using `pandas`, and want to manipulate the dataframe before sending it to the engine,
here's how you should proceed.

```python
import pandas as pd

df = pd.read_csv("fixtures/iris.csv")

# ... do some modifications on the dataset

import io

##  Convert pandas dataframe in a readable format for the engine
buffer = io.StringIO()  # The buffer will store the content of the dataframe
df.to_csv(buffer, index=False)
buffer.seek(0)

dataset = client.datasets.create_dataset(buffer)
```

The data is received as a string.
If you want to read it into a pandas DataFrame, you can do it like this

```python
data = client.datasets.download_dataset(id=dataset.id)
dataframe = pd.read_csv(io.StringIO(data))
```

### Set parameters

Here???s the list of parameters you can use for avatarization. The description for each parameter is available in our main docs.

- `k` (required)
- `column_weights`: default=1 for each variable
- `ncp`: default=5.
- `imputation`: imputation parameters type of `ImputationParameters`.

  - `k`: number of neighbors for the knn imputation. default=5
  - `method`: method used for the imputation with `ImputeMethod`, default=`ImputeMethod.knn`)
  - `training_fraction`: the fraction of the dataset used to train the knn imputer. default=1

- `seed`: default=NULL.

These can all be set using the `AvatarizationParameters` object that you can import from `avatars.models` like so

```python
from avatars.models import AvatarizationParameters

parameters = AvatarizationParameters(k=5, ncp=7, seed=42)
```

### Launch a job

One job corresponds to one avatarization.

```python
from avatars.models import JobCreate

# Pass the parameters and the dataset id to the JobCreate object...
job_create = JobCreate(dataset_id=dataset.id, parameters=parameters)

# ... and launch the avatarization by passing the JobCreate object to the create_job method
# This launches the avatarization and returns immediately
job = client.jobs.create_job(request=job_create)

# You can retrieve the result and the status of the job (if it is running, has stopped, etc...).
# This call will block until the job is done or a timeout is expired.
# You can call this function as often as you want.
job = client.jobs.get_job(id=job.id)
```

#### Retry mechanism

The `get_job` function periodically queries the avatarization engine to check if a given job is finished.
This call will block until a given timeout has expired, and then return.
However, the job is still running on the server. You can call `get_job` again, as many times as needed.
If the job is finished, the call finishes too.

You can modify this timeout by passing the `timeout` keyword to `get_job`.

```python
# Will periodically retry until 10 seconds have passed
job = client.jobs.get_job(id=job.id, timeout=10)
```

Sometimes, the job can fail. You can inspect the `Job` instance to see the status using `job.status`.

```python
print(job.status)  # prints "JobStatus.success"
```

Note that there is also the `per_request_timeout` keyword that is available. It specifies the timeout for one single request to the engine, while the `timeout` keyword is the global timeout that the method is allowed to take.
In other methods, only `timeout` is available as only a single call is made.

```python
# Will periodically retry for 10 seconds, and each request can take 2 seconds.
job = client.jobs.get_job(id=job.id, per_request_timeout=2, timeout=10)
```

### Retrieving results

```python
# Once the avatarization is finished, you can retrieve the results of the avatarization,
# most notably the privacy metrics
result = job.result
print(f"got metrics : {result.privacy_metrics}")
# For the full response, checkout the JobResponse class in models.py

# You will also be able to manipulate the avatarized dataset.
# Note that the order of the lines have been shuffled, which means that the link
# between original and avatar individuals cannot be made.
avatars_dataset_id = result.avatars_dataset.id
avatars_dataset = client.datasets.download_dataset(id=avatars_dataset_id)

# The returned dataset is a CSV file as string.
# We'll use pandas to get the data into a dataframe and io.StringIO to
# transform the string into something understandable for pandas
avatars_df = pd.read_csv(io.StringIO(avatars_dataset))
print(avatars_df.head())
```

### Evaluate privacy

You can retrieve the privacy metrics from the result object (see our main docs for details about each metric):

```python
print(result.privacy_metrics.hidden_rate)
print(result.privacy_metrics.local_cloaking)
```

### Evaluate utility 

You can evaluate your avatarization on different criteria: 

- univariate 
- bivariate
- multivariate
  
See [here](https://github.com/octopize/avatar-python/blob/main/notebooks/evaluate_quality.ipynb) a jupyter notebook example to evaluate the quality of an avatarization. 
