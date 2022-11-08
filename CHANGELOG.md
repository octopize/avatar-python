# Changelog

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
