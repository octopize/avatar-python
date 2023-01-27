User guide
==========

How to reset your password
--------------------------

**NB**: This section is only available if the use of emails to login is
activated in the global configuration. It is not the case by default.

If you forgot your password or if you need to set one, first call the
forgotten_password endpoint:

.. raw:: html

   <!-- It is python, just doing this so that test-integration does not run this code (need mail config to run)  -->

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

How to log in to the server
---------------------------

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

How to upload a dataframe
-------------------------

As a pandas dataframe

.. code:: python

   import pandas as pd

   df = pd.read_csv("fixtures/iris.csv")

   # ... do some modifications on the dataset

   dataset = client.pandas_integration.upload_dataframe(df)

as a ``.csv`` file

.. code:: python

   filename = "fixtures/iris.csv"

   with open(filename, "r") as f:
       dataset = client.datasets.create_dataset(request=f)

How to launch an avatarization with metric
------------------------------------------

You can lunch an avatarization with some simple privacy and signal
metrics.

.. code:: python

   from avatars.models import AvatarizationJobCreate, AvatarizationParameters
   job_create = AvatarizationJobCreate(parameters=parameters)
   job = client.jobs.create_full_avatarization_job(request=job_create)

   job = client.jobs.get_avatarization_job(id=job.id)
   print(job.result.privacy_metrics)
   print(job.result.avatars)

You can retrieve the result and the status of the job (if it is running,
has stopped, etc…). This call will block until the job is done or a
timeout is expired. You can call this function as often as you want.

You can modify this timeout by passing the ``timeout`` keyword to
``get_avatarization_job``.

How to launch an avatarization job only
---------------------------------------

You can launch a simple avatarization job without any metrics
computation.

.. code:: python

   job = client.jobs.create_avatarization_job(
       AvatarizationJobCreate(
           parameters=AvatarizationParameters(
               k=20,
               dataset_id=dataset.id,
           ),
       )
   )
   job = client.jobs.get_avatarization_job(job.id, timeout=10)
   print(job.status)
   print(job.result)

How to launch privacy metrics
-----------------------------

You can launch a privacy metrics with two datasets, the original and the
anonymized.

You need to enter some parameters to launch some specifics privacy
metrics.

.. code:: python

   from avatars.models import PrivacyMetricsJobCreate, PrivacyMetricsParameters

   privacy_job = client.jobs.create_privacy_metrics_job(
       PrivacyMetricsJobCreate(
           parameters=PrivacyMetricsParameters(
               original_id=dataset.id,
               unshuffled_avatars_id=job.result.sensitive_unshuffled_avatars_datasets.id,
               closest_rate_percentage_threshold=0.3,
               closest_rate_ratio_threshold=0.3,
               known_variables=[
                   "sepal.length",
                   "petal.length",
               ],
               target="variety",
               seed=42,
           ),
       )
   )

   privacy_job = client.jobs.get_privacy_metrics(privacy_job.id, timeout=10)

   print(privacy_job.status)
   print(privacy_job.result)

See `our technical
documentation <https://docs.octopize.io/docs/understanding/Privacy/>`__
for more details on all privacy metrics.

How to launch signal metrics
----------------------------

You can evaluate your avatarization on different criteria:

-  univariate
-  bivariate
-  multivariate

.. code:: python

   from avatars.models import SignalMetricsJobCreate, SignalMetricsParameters

   signal_job = client.jobs.create_signal_metrics_job(
       SignalMetricsJobCreate(
           parameters=SignalMetricsParameters(
               original_id=dataset.id,
               avatars_id=job.result.avatars_dataset.id,
               seed=42,
           ),
       )
   )

   signal_job = client.jobs.get_signal_metrics(signal_job.id, timeout=10)
   print(signal_job.status)
   print(signal_job.result)

See
`here <https://github.com/octopize/avatar-python/blob/main/notebooks/evaluate_quality.ipynb>`__
a jupyter notebook example to evaluate the quality of an avatarization.

See `our technical
documentation <https://docs.octopize.io/docs/understanding/Privacy/>`__
for more details on all signal metrics.

How to generate the report
--------------------------

You can create an avatarization report.

You need to run privacy and signal metrics with the arguments
``persistance_job_id=job.id`` before running the report.

.. code:: python

   from avatars.models import ReportCreate

   report = client.reports.create_report(
       ReportCreate(
           avatarization_job_id=job.id,
           privacy_job_id=privacy_job.id,
           signal_job_id=signal_job.id,
       ),
       timeout=1000,
   )
   result = client.reports.download_report(id=report.id)
   with open(f"./tmp/my_avatarization_report.pdf", "wb") as f:
       f.write(result)

How to launch a whole pipeline
------------------------------

We have implemented the concept of pipelines.

.. code:: python

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

See :doc:`processors <processors>`__ for more information about the
processor. See `this
notebook <https://github.com/octopize/avatar-python/blob/main/notebooks/Tutorial4_Client_side_processors.ipynb>`__
for an advanced usage of the pipeline.

How to download an avatar dataset
---------------------------------

As a pandas dataframe. The dtypes will be copied over from the original
dataframe.

Note that the order of the lines have been shuffled, which means that
the link between original and avatar individuals cannot be made.

.. code:: python

   result = job.result
   avatars_dataset_id = result.avatars_dataset.id

   avatar_df = client.pandas_integration.download_dataframe(avatars_dataset_id)
   print(avatar_df.head())

As a ``.csv`` file as string.

.. code:: python

   result = job.result
   avatars_dataset_id = result.avatars_dataset.id
   avatars_dataset = client.datasets.download_dataset(id=avatars_dataset_id)
   avatar_df = pd.read_csv(io.StringIO(avatars_dataset))
   print(avatar_df.head())

⚠ Sensitive ⚠ how to access the results unshuffled
--------------------------------------------------

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
   sensitive_unshuffled_avatars_df = client.pandas_integration.download_dataframe(
       sensitive_unshuffled_avatars_datasets_id
   )
   print(sensitive_unshuffled_avatars_df.head())
