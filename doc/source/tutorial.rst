Tutorial
========

This Python client communicates with the Avatar platform.

For more information about the Avatar method and process, check out our
main docs at https://docs.octopize.io

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
   import pandas as pd

   client = ApiClient(base_url=os.environ.get("BASE_URL"))
   client.authenticate(username="username", password="strong_password")

   df = pd.read_csv("fixtures/iris.csv")
   dataset = client.pandas_integration.upload_dataframe(df)

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
   dataset = client.datasets.download_dataset(job.result.avatars_dataset.id)

   # generate the report 
    report = client.reports.create_report(ReportCreate(job_id=job.id), timeout=1000)
    result = client.reports.download_report(id=report.id)
    with open(f"./my_avatarization_report.pdf", "wb") as f:
        f.write(result)

Avatarization step by step
--------------------------

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

One job corresponds to one avatarization. 2 methods are available to create a job: 

- (standard use) ``create_full_avatarization_job`` creates an avatarization job then computes metrics.

- (expert use) ``create_avatarization_job`` only creates an avatarization job.

.. code:: python

   from avatars.models import AvatarizationJobCreate

   # Pass the parameters to the AvatarizationJobCreate object...
   job_create = AvatarizationJobCreate(parameters=parameters)

   # ... and launch the avatarization by passing the AvatarizationJobCreate object to the create_avatarization_job method
   # This launches the avatarization and returns immediately
   job = client.jobs.create_full_avatarization_job(request=job_create)

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
   from avatars.processors import ProportionProcessor

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

