Tutorial
========

This Python client communicates with the Avatar platform.

For more information about the Avatar method and process, check out our
main docs at https://docs.octopize.io

Installation
------------

Choose the latest version at
https://github.com/octopize/avatar-python/releases

Install the package by pointing to the .whl file (replace with correct
version below).

.. code:: bash

   pip install https://github.com/octopize/avatar-python/releases/download/0.1.11/avatars-0.1.11-py3-none-any.whl
   # or, if you're using poetry (recommended)
   poetry add https://github.com/octopize/avatar-python/releases/download/0.1.11/avatars-0.1.11-py3-none-any.whl

Setup
-----

The only remaining step before using the API is setting the endpoint and
authenticating. We recommend using environment variables to provide the
password.

.. code:: python

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

The Python client library is fully type-annotated. This will let you use
interface hints from your IDE.

Quickstart
----------

This is all you need to run and evaluate an avatarization:

.. code:: python

   from avatars.client import ApiClient
   from avatars.models import AvatarizationJobCreate, AvatarizationParameters
   import os

   client = ApiClient(base_url=os.environ.get("BASE_URL"))
   client.authenticate(username="username", password="strong_password")

   dataset = client.datasets.create_dataset(open("fixtures/iris.csv", "r"))

   job = client.jobs.create_avatarization_job(
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
   dataset = client.datasets.download_dataset(job.result.avatars_dataset.id)

Avatarization step by step
--------------------------

Manipulate datasets
~~~~~~~~~~~~~~~~~~~

You can pass the data to ``create_dataset()`` directly as a file handle.

Using CSV files
^^^^^^^^^^^^^^^

.. code:: python

   filename = "fixtures/iris.csv"

   with open(filename, "r") as f:
       dataset = client.datasets.create_dataset(request=f)

Using ``pandas`` dataframes
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using ``pandas``, and want to manipulate the dataframe before
sending it to the engine, here’s how you should proceed.

.. code:: python

   import pandas as pd

   df = pd.read_csv("fixtures/iris.csv")

   # ... do some modifications on the dataset

   dataset = client.pandas_integration.upload_dataframe(df)

   job = client.jobs.create_avatarization_job(
       AvatarizationJobCreate(
           parameters=AvatarizationParameters(
               k=20,
               dataset_id=dataset.id,
           ),
       )
   )
   job = client.jobs.get_avatarization_job(job.id)

Then receive the generated avatars as a pandas dataframe:

.. code:: python

   avatars_df = client.pandas_integration.download_dataframe(job.result.avatars_dataset.id)

The dtypes will be copied over from the original dataframe.

Setting the avatarization parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here’s the list of parameters you can use for avatarization. The
description for each parameter is available in our main docs.

-  ``k`` (required)
-  ``dataset_id`` (required): id of the dataset to avatarize
-  ``column_weights``: default=1 for each variable
-  ``ncp``: default=5.
-  ``imputation``: imputation parameters type of
   ``ImputationParameters``.

   -  ``k``: number of neighbors for the knn imputation. default=5
   -  ``method``: method used for the imputation with ``ImputeMethod``,
      default=\ ``ImputeMethod.knn``)
   -  ``training_fraction``: the fraction of the dataset used to train
      the knn imputer. default=1

-  ``seed``: default=NULL.

These can all be set using the ``AvatarizationParameters`` object that
you can import from ``avatars.models`` like so

.. code:: python

   from avatars.models import AvatarizationParameters

   parameters = AvatarizationParameters(dataset_id=dataset.id, k=5, ncp=7, seed=42)

Launch an avatarization job
~~~~~~~~~~~~~~~~~~~~~~~~~~~

One job corresponds to one avatarization.

.. code:: python

   from avatars.models import AvatarizationJobCreate

   # Pass the parameters to the AvatarizationJobCreate object...
   job_create = AvatarizationJobCreate(parameters=parameters)

   # ... and launch the avatarization by passing the AvatarizationJobCreate object to the create_avatarization_job method
   # This launches the avatarization and returns immediately
   job = client.jobs.create_avatarization_job(request=job_create)

   # You can retrieve the result and the status of the job (if it is running, has stopped, etc...).
   # This call will block until the job is done or a timeout is expired.
   # You can call this function as often as you want.
   job = client.jobs.get_avatarization_job(id=job.id)

Retry mechanism
^^^^^^^^^^^^^^^

The ``get_avatarization_job`` function periodically queries the
avatarization engine to check if a given job is finished. This call will
block until a given timeout has expired, and then return. However, the
job is still running on the server. You can call
``get_avatarization_job`` again, as many times as needed. If the job is
finished, the call finishes too.

You can modify this timeout by passing the ``timeout`` keyword to
``get_avatarization_job``.

.. code:: python

   # Will periodically retry until 10 seconds have passed
   job = client.jobs.get_avatarization_job(id=job.id, timeout=10)

Sometimes, the job can fail. You can inspect the ``Job`` instance to see
the status using ``job.status``.

.. code:: python

   print(job.status)  # prints "JobStatus.success"

Note that there is also the ``per_request_timeout`` keyword that is
available. It specifies the timeout for one single request to the
engine, while the ``timeout`` keyword is the global timeout that the
method is allowed to take. In other methods, only ``timeout`` is
available as only a single call is made.

.. code:: python

   # Will periodically retry for 10 seconds, and each request can take 2 seconds.
   job = client.jobs.get_avatarization_job(id=job.id, per_request_timeout=2, timeout=10)

Retrieving results
~~~~~~~~~~~~~~~~~~

.. code:: python

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

Evaluate privacy
~~~~~~~~~~~~~~~~

You can retrieve the privacy metrics from the result object (see our
main docs for details about each metric):

.. code:: python

   print(result.privacy_metrics.hidden_rate)
   print(result.privacy_metrics.local_cloaking)

Evaluate utility
~~~~~~~~~~~~~~~~

You can evaluate your avatarization on different criteria:

-  univariate
-  bivariate
-  multivariate

See
`here <https://github.com/octopize/avatar-python/blob/main/notebooks/evaluate_quality.ipynb>`__
a jupyter notebook example to evaluate the quality of an avatarization.

⚠ Sensitive ⚠ Access the results unshuffled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You might want to access the avatars dataset prior to being shuffled.
**WARNING**: There is no protection at all, as the linkage between the
unshuffled avatars dataset and the original data is obvious. **This
dataset contains sensitive data**. You will need to shuffle it in order
to make it safe.

.. code:: python

   # Note that the order of the lines have NOT been shuffled, which means that the link
   # between original and avatar individuals IS OBVIOUS.
   sensitive_unshuffled_avatars_datasets_id = (
       result.sensitive_unshuffled_avatars_datasets.id
   )
   sensitive_unshuffled_avatars_datasets = client.datasets.download_dataset(
       id=sensitive_unshuffled_avatars_datasets_id
   )

   # The returned dataset is a CSV file as string.
   # We'll use pandas to get the data into a dataframe and io.StringIO to
   # transform the string into something understandable for pandas
   sensitive_unshuffled_avatars_df = pd.read_csv(
       io.StringIO(sensitive_unshuffled_avatars_datasets)
   )
   print(avatars_df.head())

Launch a whole pipeline
-----------------------

We have implemented the concept of pipelines.

.. code:: python

   import pandas as pd

   from avatars.client import ApiClient
   from avatars.models import (
       AvatarizationJobCreate,
       AvatarizationParameters,
   )
   from avatars.models import AvatarizationPipelineCreate
   from avatars.processors.proportions import ProportionProcessor

   df = pd.DataFrame(
       {
           "variable_1": [100, 150, 120, 100],
           "variable_2": [10, 30, 30, 22],
           "variable_3": [30, 60, 30, 35],
           "variable_4": [60, 60, 60, 65],
       }
   )

   dataset = client.pandas_integration.upload_dataframe(df)


   proportion_processor = ProportionProcessor(
       variable_names=["variable_2", "variable_3", "variable_4"],
       reference="variable_1",
       sum_to_one=True,
   )

   result = client.pipelines.avatarization_pipeline_with_processors(
       AvatarizationPipelineCreate(
           avatarization_job_create=AvatarizationJobCreate(
               parameters=AvatarizationParameters(dataset_id=dataset.id, k=3),
           ),
           processors=[proportion_processor],
           df=df,
       )
   )

Reset your password
-------------------

**NB**: This section is only available if the use of emails to login is
activated in the global configuration. It is not the case by default.

If you forgot your password or if you need to set one, first call the
forgotten_password endpoint:

.. code:: javascript

   from avatars.client import ApiClient

   client = ApiClient(base_url=os.environ.get("BASE_URL"))
   client.forgotten_password("yourmail@mail.com")

You’ll then receive an email containing a token. This token is only
valid once, and expires after 24 hours. Use it to reset your password:

.. code:: javascript

   from avatars.client import ApiClient

   client = ApiClient(base_url=os.environ.get("BASE_URL"))
   client.reset_password("yourmail@mail.com", "new_password", "new_password", "token-received-by-mail")

You’ll receive an email confirming your password was reset.
