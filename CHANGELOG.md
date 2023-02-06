# Changelog

## 0.3.0

### BREAKING

- `ReportCreate` now takes required `avatarization_job_id`, `signal_job_id`, and `privacy_job_id` parameters
- Mark `AvatarizationParameters.to_categorical_threshold` as deprecated
- `client.jobs.create_avatarization_job` behaviour does not compute metrics anymore. Use `client.jobs.create_full_avatarization_job` instead
- `AvatarizationResult` now has `signal_metrics` and `privacy_metrics` properties as `Optional`
- Verify dataset size on upload. This will prevent you from uploading a dataset that is too big to handle for the server
- The `direct_match_protection` privacy metrics got renamed to `column_direct_match_protection`
- `dataset_id` from `AvatarizationParameters` is now required
- `dataset_id` from `AvatarizationJob`,`SignalMetricsJob` and `PrivacyMetricsJob` got removed
- `client.users.get_user` now accepts an `id` rather than a `username`
- `SignalMetricsParameters.job_id` got renamed to `persistance_job_id`
- `CreateUser` does not take `is_email_confirmed` as parameter anymore
- Processors get imported from `avatars.processors` instead of `avatars.processor.{processor_name}`
  - Example: `from avatars.processors.expected_mean import ExpectedMeanProcessor` becomes `from avatars.processors import ExpectedMeanProcessor`

### Others

- feat: add more metrics and graphs to report
- feat: add `client.compatibility.is_client_compatible` to verify client-server compatibility
- feat: enable to avatarize without calculating metrics using `client.jobs.create_avatarization_job`
- feat: add `nb_dimensions` property to `Dataset`
- feat: add `User` object
- feat: use `patch` in `client.datasets.create_dataset` to patch dataset columns on upload
- feat: add `correlation_protection_rate`, `inference_continuous`, `inference_categorical`, `row_direct_match_protection` and `closest_rate` privacy metrics
- feat: add `known_variables`, `target`, `closest_rate_percentage_threshold`, and `closest_rate_ratio_threshold` to `PrivacyMetricsParameters`
- docs: add multiple versions of the documentation
- feat: each user now belongs to an organization and gets a new field: `organization_id`
- fix: fixed a bug where computing privacy metrics with distinct missing values was impossible

## 0.2.2

- Improve type hints of the method
- Update tutorial notebooks with smaller datasets
- Fix bugs in tutorial notebooks
- Improve error message when the call to the API times out
- Add `jobs.find_all_jobs_by_user`
- Add two new privacy metrics: `direct_match_protection` and `categorical_hidden_rate`
- Add the `DatetimeProcessor`

## 0.2.1

- Fix to processor taking the wrong number of arguments
- Make the `toolz` package a mandatory dependency
- Fix a handling of a target variable equaling zero

## 0.2.0

- Drop support for python3.8 # BREAKING CHANGE
- Drop `jobs.get_job` and `job.create_job`. # BREAKING CHANGE
- Rename `DatasetResponse` to `Dataset` # BREAKING CHANGE
- Rename `client.pandas` to `client.pandas_integration` # BREAKING CHANGE
- Add separate endpoint to compute metrics separately using `jobs.create_signal_metrics_job` and `jobs.create_privacy_metrics_job`.
- Add separate endpoint to access metrics jobs using `jobs.get_signal_metrics` and `job.get_privacy_metrics`
- Add processors to pre- and post-process your data before, and after avatarization for custom use-cases. These are accessible under `avatars.processors`.
- Handle errors more gracefully
- Add ExcludeCategoricalParameters to use embedded processor on the server side

## 0.1.16

- Add forgotten password endpoint
- Add reset password endpoint
- JobParameters becomes AvatarizationParameters
- Add DCR and NNDR to privacy metrics

## 0.1.15

- Handle category dtype
- Fix dtype casting of datetime columns
- Add ability to login with email
- Add filtering options to `find_users`
- Avatarizations are now called with `create_avatarization_job` and `AvatarizationJobCreate`.
  `create_job` and `JobCreate` are deprecated but still work.
- `dataset_id` is now passed to `AvatarizationParameters` and not `AvatarizationJobCreate`.
- `Job.dataset_id` is deprecated. Use `Job.parameters.dataset_id` instead.

### BREAKING

- Remove `get_health_config` call.

## 0.1.14

- Give access to avatars unshuffled avatars dataset

## 0.1.13

- Remove default value for `to_categorical_threshold`
- Use `logger.info` instead of `print`
