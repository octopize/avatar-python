# Changelog

## 0.2.0

- Drop support for python3.8 # BREAKING CHANGE
- Drop `jobs.get_job` and `job.create_job`. # BREAKING CHANGE
- Rename `DatasetResponse` to `Dataset` # BREAKING CHANGE
- Rename `client.pandas` to `client.pandas_integration`
- Add separate endpoint to compute metrics separately using `jobs.create_signal_metrics_job` and `jobs.create_privacy_metrics_job`.
- Add separate endpoint to access metrics jobs using `jobs.get_signal_metrics` and `job.get_privacy_metrics`
- Add processors to pre- and post-process your data before, and after avatarization for custom use-cases. These are accessible under `avatars.processors`.

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
