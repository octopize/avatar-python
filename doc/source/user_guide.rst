User guide
==========

-  `User guide <#user-guide>`__

   -  `How to setup your email
      account <#how-to-setup-your-email-account>`__
   -  `How to reset your password <#how-to-reset-your-password>`__
   -  `How to log in to the server <#how-to-log-in-to-the-server>`__
   -  `How to check compatibility <#how-to-check-compatibility>`__
   -  `How to upload a data <#how-to-upload-a-data>`__

      -  `As a pandas dataframe <#as-a-pandas-dataframe>`__
      -  `As a csv file <#as-a-csv-file>`__

   -  `How to do a first analysis of your
      dataset <#how-to-do-a-first-analysis-of-your-dataset>`__
   -  `How to launch an avatarization with
      metrics <#how-to-launch-an-avatarization-with-metrics>`__
   -  `How to launch an avatarization job
      only <#how-to-launch-an-avatarization-job-only>`__
   -  `How to launch privacy metrics <#how-to-launch-privacy-metrics>`__
   -  `How to launch signal metrics <#how-to-launch-signal-metrics>`__

      -  `How to set the avatarization
         parameters <#how-to-set-the-avatarization-parameters>`__

   -  `How to generate the report <#how-to-generate-the-report>`__

      -  `Create report from jobs <#create-report-from-jobs>`__
      -  `Create report from data <#create-report-from-data>`__

   -  `How to launch a whole
      pipeline <#how-to-launch-a-whole-pipeline>`__
   -  `How to download an avatar
      dataset <#how-to-download-an-avatar-dataset>`__

      -  `As a pandas dataframe <#as-a-pandas-dataframe-1>`__
      -  `As a csv formatted string <#as-a-csv-formatted-string>`__

   -  `How to handle a large dataset <#how-to-handle-a-large-dataset>`__

      -  `Handle large amount of rows <#handle-large-amount-of-rows>`__
      -  `Handle large amount of
         dimensions <#handle-large-amount-of-dimensions>`__

   -  `Handling timeouts <#handling-timeouts>`__

      -  `Asynchronous calls <#asynchronous-calls>`__
      -  `Synchronous calls <#synchronous-calls>`__

   -  `SENSITIVE: how to access the results
      unshuffled <#sensitive-how-to-access-the-results-unshuffled>`__

How to setup your email account
-------------------------------

*This section is only needed if the use of emails to login is activated
in the global configuration. It is not the case by default.*

At the moment, you have to get in touch with your Octopize contact so
that they can create your account.

Our current email provider is AWS. They need to verify an email address
before our platform can send emails to it.

You’ll thus get an email from AWS asking you to verify your email by
clicking on a link. Once you have verified your email address by
clicking on that link, you can follow the steps in the section about
`reset password <#how-to-reset-your-password>`__.

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

   import pandas as pd
   import io

   # Change this to your actual server endpoint, e.g. base_url="https://avatar.company.com"
   client = ApiClient(base_url=os.environ.get("AVATAR_BASE_URL"))
   client.authenticate(
       username=os.environ.get("AVATAR_USERNAME"),
       password=os.environ.get("AVATAR_PASSWORD"),
   )

How to check compatibility
--------------------------

After authentication, you can check whether you can communicate with the
server with

.. code:: python

   # Verify that we can connect to the API server
   client.health.get_health()

You can also check if the version of your client is compatible with the
server you are running, and see if it is up-to-date. We frequently
release new versions of the server and client that provide bugfixes and
feature improvements, so be on the look out for these updates.

.. code:: python

   # Verify that the client is compatible.
   client.compatibility.is_client_compatible()

How to upload a data
--------------------

As a pandas dataframe
~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   import pandas as pd

   df = pd.read_csv("fixtures/iris.csv")

   # ... do some modifications on the dataset

   dataset = client.pandas_integration.upload_dataframe(df)

As a csv file
~~~~~~~~~~~~~

.. code:: python

   filename = "fixtures/iris.csv"

   with open(filename, "r") as f:
       dataset = client.datasets.create_dataset(request=f)

How to do a first analysis of your dataset
------------------------------------------

Sometimes it’s useful to gather information about the dataset and how it
will be perceived by the avatarization engine.

For that, you can use the ``analyze_dataset`` method that will analyze
the dataset and return useful information, such as the dimensions of the
data.

.. code:: python

   import time
   from avatars.models import AnalysisStatus

   dataset = client.datasets.analyze_dataset(dataset.id)

   while dataset.analysis_status != AnalysisStatus.done:
       dataset = client.datasets.get_dataset(dataset.id)
       time.sleep(1)

   print(f"Lines: {dataset.nb_lines}, dimensions: {dataset.nb_dimensions}")

How to launch an avatarization with metrics
-------------------------------------------

You can launch an avatarization with some privacy and signal metrics.

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

You can launch a privacy metrics job with two datasets, the original and
the anonymized.

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
documentation <https://docs.octopize.io/docs/understanding/Utility/>`__
for more details on all signal metrics.

How to set the avatarization parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See our `Avatarization
parameters <https://docs.octopize.io/docs/using/running>`__
documentation for more information about the parameters.

These can all be set using the ``AvatarizationParameters`` object that
you can import from ``avatars.models``:

.. code:: python

   from avatars.models import (
       AvatarizationParameters,
       ExcludeCategoricalParameters,
       ImputationParameters,
       ExcludeCategoricalMethod,
   )


   imputation = ImputationParameters(method="mode", k=8, training_fraction=0.3)
   exclude_parameters = ExcludeCategoricalParameters(
       exclude_cardinality_threshold=10,
       exclude_replacement_strategy=ExcludeCategoricalMethod(
           "exclude_replacement_strategy"
       ),
   )
   parameters = AvatarizationParameters(
       dataset_id=dataset.id,
       k=25,
       ncp=10,
       imputation=imputation,
       exclude_categorical=exclude_parameters,
   )

How to generate the report
--------------------------

Create report from jobs
~~~~~~~~~~~~~~~~~~~~~~~

You can create an avatarization report after having executed all of the
following jobs:

-  an avatarization job
-  a signal metrics job
-  a privacy metrics job

.. code:: python

   from avatars.models import ReportCreate

   report = client.reports.create_report(
       ReportCreate(
           avatarization_job_id=job.id,
           privacy_job_id=privacy_job.id,
           signal_job_id=signal_job.id,
       ),
       timeout=30,
   )
   result = client.reports.download_report(id=report.id)
   with open(f"./tmp/my_avatarization_report.pdf", "wb") as f:
       f.write(result)

Create report from data
~~~~~~~~~~~~~~~~~~~~~~~

You can create an avatarization report from datasets and metric jobs.

.. code:: python

   from avatar.models import ReportFromDataCreate

   report = client.reports.create_report_from_data(
       ReportFromDataCreate(
           dataset_id=dataset.id,
           avatars_dataset_id=avatar_dataset.id,
           privacy_job_id=privacy_job.id,
           signal_job_id=signal_job.id,
       ),
       timeout=30,
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
               parameters=AvatarizationParameters(dataset_id=dataset.id, k=20),
           ),
           processors=[proportion_processor],
           df=df,
       )
   )

See `processors <processors.html>`__ for more information about the
processors. See `this
notebook <https://github.com/octopize/avatar-python/blob/main/notebooks/Tutorial4_Client_side_processors.ipynb>`__
for an advanced usage of the pipeline.

How to download an avatar dataset
---------------------------------

.. _as-a-pandas-dataframe-1:

As a pandas dataframe
~~~~~~~~~~~~~~~~~~~~~

The dtypes will be copied over from the original dataframe.

Note that the order of the lines have been shuffled, which means that
the link between original and avatar individuals cannot be made.

.. code:: python

   result = job.result
   avatars_dataset_id = result.avatars_dataset.id

   avatar_df = client.pandas_integration.download_dataframe(avatars_dataset_id)
   print(avatar_df.head())

As a csv formatted string
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   result = job.result
   avatars_dataset_id = result.avatars_dataset.id
   avatars_dataset = client.datasets.download_dataset(id=avatars_dataset_id)
   avatar_df = pd.read_csv(io.StringIO(avatars_dataset))
   print(avatar_df.head())

How to handle a large dataset
-----------------------------

Due to the server limit, you can be limited by the number of row and the
number of dimension.

Handle large amount of rows
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to anonymize a large number of records, you can use the
batch methodology. Your dataset will be split into batches and each
batch will be anonymized independently from the others.

Metrics are computed on each batch of the data. The average of all the
signal metrics is computed. For the privacy metrics, we return the worst
and the mean of all metrics. You can also access to all batch metrics
for specific use cases (such as debugging).

See this `notebook
tutorial <https://github.com/octopize/avatar-python/blob/main/notebooks/Tutorial7-Batch_avatarization.ipynb>`__
for more information about batch use.

Handle large amount of dimensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The number of dimensions is the number of continuous variables plus the
number of modalities in categorical variables. The limit of dimension is
frequently reached due to a large number of modalities in one/sample of
categorical variables.

There are several solutions to bypass this limitation: - Encode the
categorical variable into a continuous variable (frequency encoding,
target encoding, …). - Reduce the number of modalities by grouping some
into more general modalities. - Use the argument
``use_categorical_reduction`` (Beta version)

The parameter ``use_categorical_reduction`` will reduce the dimension of
the categorical variable by encoding them as vectors. This step is using
the word embedding cat2vec. This solution could reduce the utility of
your dataset.

Handling timeouts
-----------------

Asynchronous calls
~~~~~~~~~~~~~~~~~~

A lot of endpoints of the Avatar API are asynchronous, meaning that you
request something that will run in the background, and will return a
result after some time using another method, like
``get_avatarization_job`` for ``create_avatarization_job``.

The default timeout for most of the calls to the engine is not very
high, i.e. a few seconds long. You will quite quickly reach a point
where a job on the server is taking longer than that to run.

The calls being asynchronous, you don’t need to sit and wait for the job
to finish, you can simply take a break, come back after some time, and
run the method requesting the result again.

Example:

.. code:: python

   job = client.jobs.create_avatarization_job(
       AvatarizationJobCreate(
           parameters=AvatarizationParameters(
               k=20,
               dataset_id=dataset.id,
           ),
       )
   )

   print(job.id)  # make sure to gather the ID

   print(job.status)  # JobStatus.pending
   # Take a coffee break, close the script, come back in 10 minutes

   finished_job = client.jobs.get_avatarization_job(job.id)

   print(finished_job.status)  # JobStatus.success

However, sometimes you want your code to be blocking and wait for the
job to finish, and only then return the result.

For that, you can simply increase the timeout:

.. code:: python

   # Will retry for 10 minutes, or until the job is finished.
   finished_job = client.jobs.get_avatarization_job(job.id, timeout=600)

Synchronous calls
~~~~~~~~~~~~~~~~~

Synchronous calls are calls that are blocking, which means that the
interpreter runs your line of code and waits until there is a result
before continuing on with the rest of the script.

For instance, uploading or downloading a dataset can be time-consuming
if the dataset is large.

Should you encounter issues with the upload timing out, you can increase
the timeout like so:

.. code:: python

   dataset = client.pandas_integration.upload_dataframe(df, timeout=20)

Under normal circumstances, that should be sufficient.

However, if your file is particularly big, or the server is under high
load, the call might be interrupted and you will be left with a nasty
exception, similar to:

-  ``stream timeout``
-  ``RemoteProtocolError: peer closed connection without sending complete message body (received XXXXXX bytes, expected YYYYYY)``

Under these circumstances, we recommend uploading the file as stream,
which you can do by setting the flag ``should_stream`` to ``True`` on
``upload_dataframe``/``download_dataframe`` or
``create_dataset``/``download_dataset``.

.. code:: python

   dataset = client.pandas_integration.upload_dataframe(df, should_stream=True)

This will make sure that the file is not stored in it’s entirety on the
server’s memory, but only chunks of it, which will reduce the likelihood
of a timeout occurring during the file transfer.

SENSITIVE: how to access the results unshuffled
-----------------------------------------------

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
