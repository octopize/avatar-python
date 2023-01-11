Changelog
=========

0.2.2
-----

-  Improve type hints of the method
-  Update tutorial notebooks with smaller datasets
-  Fix bugs in tutorial notebooks
-  Improve error message when the call to the API times out
-  Add ``jobs.find_all_jobs_by_user``
-  Add two new privacy metrics: ``direct_match_protection`` and
   ``categorical_hidden_rate``
-  Add the ``DatetimeProcessor``

.. _section-1:

0.2.1
-----

-  Fix to processor taking the wrong number of arguments
-  Make the ``toolz`` package a mandatory dependency
-  Fix a handling of a target variable equaling zero

.. _section-2:

0.2.0
-----

-  Drop support for python3.8 # BREAKING CHANGE
-  Drop ``jobs.get_job`` and ``job.create_job``. # BREAKING CHANGE
-  Rename ``DatasetResponse`` to ``Dataset`` # BREAKING CHANGE
-  Rename ``client.pandas`` to ``client.pandas_integration`` # BREAKING
   CHANGE
-  Add separate endpoint to compute metrics separately using
   ``jobs.create_signal_metrics_job`` and
   ``jobs.create_privacy_metrics_job``.
-  Add separate endpoint to access metrics jobs using
   ``jobs.get_signal_metrics`` and ``job.get_privacy_metrics``
-  Add processors to pre- and post-process your data before, and after
   avatarization for custom use-cases. These are accessible under
   ``avatars.processors``.
-  Handle errors more gracefully
-  Add ExcludeCategoricalParameters to use embedded processor on the
   server side

.. _section-3:

0.1.16
------

-  Add forgotten password endpoint
-  Add reset password endpoint
-  JobParameters becomes AvatarizationParameters
-  Add DCR and NNDR to privacy metrics

.. _section-4:

0.1.15
------

-  Handle category dtype
-  Fix dtype casting of datetime columns
-  Add ability to login with email
-  Add filtering options to ``find_users``
-  Avatarizations are now called with ``create_avatarization_job`` and
   ``AvatarizationJobCreate``. ``create_job`` and ``JobCreate`` are
   deprecated but still work.
-  ``dataset_id`` is now passed to ``AvatarizationParameters`` and not
   ``AvatarizationJobCreate``.
-  ``Job.dataset_id`` is deprecated. Use ``Job.parameters.dataset_id``
   instead.

BREAKING
~~~~~~~~

-  Remove ``get_health_config`` call.

.. _section-5:

0.1.14
------

-  Give access to avatars unshuffled avatars dataset

.. _section-6:

0.1.13
------

-  Remove default value for ``to_categorical_threshold``
-  Use ``logger.info`` instead of ``print``
