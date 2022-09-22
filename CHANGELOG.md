# Changelog

## Unreleased

- Handle category dtype
- Fix dtype casting of datetime columns
- Add ability to login with email
- Add filtering options to `find_users`
  BREAKING

- Rename `JobCreate` to `AvatarizationJobCreate`
- Move `JobCreate.dataset_id` to `AvatarizationParameters`
- Remove `get_health_config` call.
- Fix typo in `sensitive_unshuffled_avatars_dataset` variable

## 0.1.14

- Give access to avatars unshuffled avatars dataset

## 0.1.13

- Remove default value for `to_categorical_threshold`
- Use `logger.info` instead of `print`
