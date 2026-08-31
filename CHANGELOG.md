# Changelog

## NEXT RELEASE

## 1.29.0 - 2026/08/10

## 1.28.0 - 2026/08/07

### Features

- **api**: inherit the previous client version's compatible API versions (#6564)

### Bug Fixes

- **client/python**: drop the stale changelog.rst from the release file list (#6594)

## 1.27.0 - 2026/08/06

### Features

- **api**: add StorageLocation and validate volume URLs at resource ingest (#6479)
- **core**: accept and impute NaN in time series value columns (#6476)
- **api**: decouple client releases from API releases via the compatibility mapping bucket (#6442)
- **avatar**: add n time steps handling in time series (fixes #6334) (#6353)

### Bug Fixes

- **api**: don't raise when stopping an unconnected dask client (#6560)
- **avatar**: stop reporting an expected-missing holdout mapping as an error (#6557)
- **api**: accept and return the /access?url= envelope again (#6533)
- **api**: handle authlib OAuth errors in the SSO callback (#6515)
- **api**: retry local Dask cluster start when its random port is taken (#6520)
- **api**: resolve job results through StorageLocation before reading them (#6481)
- **api**: resolve /access URLs to a StorageLocation instead of substring matching (#6480)
- **api**: give the compatibility mapping opt-out a value that survives env_ignore_empty (#6484)
- **avatar**: derive the signal-metrics processor chain from the holdout half too (#6473)
- **api**: add ownership check to GET /api-keys/{id} (#6411)
- **avatar**: embed the holdout half in the Cat2Vec space (#6460)
- **api**: trust the public CAs when fetching the compatibility mapping (#6456)
- **avatar**: account for the holdout half when building the metrics processors (#6448)
- **api**: declare API 3.0.0 in the compatibility mapping and block silent major skips (#6441)
- **avatar**: skip dtype check on dropped columns in time series (#6418)
- **api**: add client 1.26.0 to compatibility mapping (#6380)

## 1.26.0 - 2026/07/27

### Features

- **avatar**: add always-on per-stage wall-time instrumentation (#6315)
- **client/python**: allow user to choose output format of files (#6275)
- **avatar**: drop col with unseen values in projection metrics (#6229)

### Bug Fixes

- **client/python**: ruffs related fixes
- **api**: defer Dask cluster startup until job creation (#6366)
- **avatar**: validate InterRecordRangeDifference columns at verify stage (#6320)
- **api**: retry transient Authentik failures and return 503 on refresh (#6300)
- **avatar**: use input format as output format of files (#6267)

## 1.25.0 - 2026/07/09

### Breaking Changes

- BREAKING **reportgenerator**: replace pdfgenerator (Markdown/LaTeX pipeline) with embedded Typst-only. (#6200)

### Features

- **core**: advice primary key even on single table context (#6199)
- **api**: replace hardcoded INITIAL_CREDIT with per-tier initial_credits + cosmetic changes (#6228)
- **api**: create 4 license tiers and feature restrictions (#6189)
- **core**: remove avatar mention from technical report (#6142)
- **avatar**: remove avatar mention by processed in PIA report (#6066)
- **avatar**: stratify row order assignement with DA (#5899)
- **avatar**: flag a processing type on columns (#6003)
- **avatar**: add split for holdout (#5958)
- **avatar**: extend link-method check to id-only tables in multitable schema (#5932)
- **client/python**: allow skipping figure computation with Runner.compute_figures (#5979)
- **avatar**: add parameter to toggle figure computation (#5959)

### Bug Fixes

- **core**: sort collections in mismatch error messages across avatar and core (#6286)
- **api**: use job.name for job audit URNs (#6084)
- **avatar**: fix PIA table header text color and remove spaces before colons in EN templates (#6236)
- **core**: bump pandas to 3.0 and fix pandas-3 compatibility issues (#6208)
- **avatar**: remove stale markdown code fences from FR AIPD sub-templates (#6230)
- **avatar**: fix failing tests after #6167 (#6211)
- **avatar**: raise error on id only TS (#6167)
- **core**: cast datetime64[D] to us before fancy indexing (#6185)
- **api**: update how dask worker is launched (#6177)
- **core**: upgrade tslearn to >=0.7.0 for Python 3.13 compatibility (#6157)
- **core**: escape Faker-only placeholders in SPECIFIC_ID patterns (#6159)
- **avatar**: align pseudonymization report dict keys with template (#6154)
- **avatar**: filter out pseudo columns for figures (#6143)
- **client/python**: validate API key at Manager creation time (#6117)
- **api**: raise a clear error message on job not found (#6096)
- **avatar**: exclude temporary tables from results metadata (#6007)
- **api**: store SSO OAuth state in the session middleware (#5315)

## 1.24.0 - 2026/06/08

### Breaking Changes

- BREAKING **api**: remove unused file access JWT secret (#5693)

### Features

- **client/python**: allow to drop a column in add_table (#5915)
- **avatar**: auto-detect ISO 8601 datetime columns in CSV files (#5898)
- **core**: add pool design for fake data strategy and improve perf (#5662)

### Bug Fixes

- **api**: return LicenseError to user with generic message (#5956)
- **avatar**: no errors if all columns are pseudonymized or frozen (#5895)
- **avatar**: prepare core, avatar, and dp packages for pandas 3 migration (#5921)
- **avatar**: annotate global_dict for mypy 2.x [var-annotated] (#5914)
- **avatar**: update corrupted_unicode.csv fixture for chardet 7.x (#5920)
- **core**: upgrade sphinx to 9.x and fix autodoc-typehints compatibility (#5917)
- **api**: prevent bulk job deletion from raising errors and improve performance (#5865)
- **api**: remove DB admin secrets from runtime API health checks (#5706)
- **core**: do not plot 3d graph with less than 3 dimensions (#5851)
- **avatar**: put back error on k>n (#5841)

## 1.23.0 - 2026/05/20

### Features

- **api**: add filtering functions to get jobs (#5694)
- **api**: sync job updates to product analytics via updated_at (#5579)

### Bug Fixes

- **client/python**: return job status when creating a runner from name (#5756)
- **avatar**: support quoted newlines in csv readers (#5681)
- **avatar**: reject empty csv uploads (#5679)
- **api**: scan all Sentry envelopes for error event in flaky integration tests (#5650)
- **core**: pin random seed in signal fixture to eliminate flaky test (#5651)

## 1.22.0 - 2026/05/06

## 1.21.0 - 2026/04/28

## 1.20.0 - 2026/04/02

## 1.19.0 - 2026/03/20

## 1.18.0 - 2026/03/16

## 1.17.0 - 2026/02/25

## 1.16.0 - 2026/02/18

## 1.15.0 - 2026/01/20

## 1.14.0 - 2026/01/19

## 1.13.0 - 2026/01/07

## 1.12.0 - 2025/12/22

- feat: add PIA report customization options

## 1.11.0 - 2025/12/17

- feat: add data_augmentation parameters to avatarization job

## 1.10.0 - 2025/12/16

## 1.9.0 - 2025/12/10

## 1.8.0 - 2025/12/02

## 1.7.0 - 2025/11/14

## 1.6.0 - 2025/11/05

## 1.5.0 - 2025/10/23

## 1.4.0 - 2025/10/22

## 1.3.0 - 2025/10/14

## 1.2.0 - 2025/10/08

## 1.1.0 - 2025/09/23

## 1.0.10 - 2025/09/15

## 1.0.9 - 2025/08/26

- BREAKING: deprecated ratio and distance thresholds

## 1.0.8 - 2025/07/25

- feat : add endpoint to render plots

## 1.0.7 - 2025/07/16

- refactor: improve results download
- fix: compliance with the new api version

## 1.0.6 - 2025/07/03

- fix: compliance with the new api version

## 1.0.5 - 2025/05/26

- fix: use specific avatar-yaml version

## 1.0.4 - 2025/05/20

- feat: support generating multitable reports
- feat: add advisor functionality

## 1.0.3 - 2025/04/30

- feat: make mandatory a set_name in the runner

## 1.0.2 - 2025/04/29

- BREAKING: feat: Release of the python client for the API 1.0.0 🚀 🥳.
- feat: New documentation of the python client.

## 0.15.0 - 2024/08/26

- feat: add tutorial on job management
- feat: add GeolocationNormalizationProcessor
- chore: remove timeout to avoid re-POST
- BREAKING: chore: remove all batch from client side

## 0.14.0 - 2024/08/07

- BREAKING: remove deprecated persistance_job_id
- BREAKING: remove deprecated to_categorical_threshold

## 0.13.0 - 2024/07/24

- BREAKING: send the total size of the stream at the start of the stream
- Remove dependency on libmagic

## 0.12.0 - 2024/07/05

- BREAKING: refactor: Dataset.columns is required

## 0.11.0 - 2024/07/01

- BREAKING: fix dataset upload

## 0.10.0 - 2024/06/18

- BREAKING: fix dataset upload

## 0.9.2 - 2024/06/11

- feat: retry any kind of network error

## 0.9.1 - 2024/06/10

- feat: retry on DNS resolution errors

## 0.9.0 - 2024/06/06

- feat: add categorical hidden rate variable to privacy parameters
- BREAKING refactor: categorical hidden rate is optional in PrivacyMetrics

## 0.8.0 - 2024/06/05

- BREAKING feat: add linkage methods to TableLink and make linear sum assignment the default method.
- BREAKING refactor: remove `ExcludeCategoricalParameters` and replace it by `ExcludeVariablesParameters`

## 0.7.4 - 2024/05/15

- Add advice for choosing avatarization parameters
- Speed up projector load and save
- Remove dataset_id from get_variable_contributions
- Add size agnostic bi-directional arrow/parquet streaming utilities

## 0.7.3 - 2024/04/29

- Allow passing filetype in datasets.download_dataset and pandas_integration.download_dataframe to change the format of the retrieved data
- Deprecate datasets.download_dataset_as_stream and datasets.create_dataset_from_stream
- Deprecate the 'should_stream' argument from pandas_integration.upload_dataframe and pandas_integration.download_dataframe
- Deprecate 'request' argument from datasets.create_dataset in favor of 'source' argument
- Add 'destination' argument to datasets.download_dataset

## 0.7.2 - 2024/04/12

- fix: remove retry logic around Job.last_updated_at

## 0.7.1 - 2024/04/11

- feat: overhaul client architecture

## 0.7.0- 2024/04/05

- fix: change shuffle multi-table process to return the right dataframe
- fix: return metric parameter error to user
- feat: return error to user if data contains ninf
- feat: improve multi-table anonymization quality (utility)
- feat: verify compatibility with server on client init
- feat: add dataset name in the multitable privacy metrics
- feat: create privacy geolocation assessment feature
- refactor: add custom methods for Datasets
- refactor: change seed place for avatarization and metrics job parameters to guarantee reproducibility

## 0.6.2

- feat: add should_verify_ssl to ApiClient to bypass
- refactor: revert to AvatarizationParameters.dataset_id being required
- feat: add pydantic constraints to privacy metrics fields
- feat: add multi table avatarization and privacy metrics jobs
- feat: add 'name' keyword argument to create_dataset

## 0.6.1

- feat: enable parquet format for dataset upload
- feat: use pydantic v2
- feat: add InterRecordBoundedCumulatedDifferenceProcessor
- fix: max file size error message

## 0.6.0

- feat: detect potential id columns
- feat: add created_at, kind to Jobs
- feat: add time series

## 0.5.2

- feat: add InterRecordBoundedRangeDifferenceProcessor

## 0.5.1

- fix: compatibility mapping due to breaking change

### BREAKING CHANGE

- remove broken endpoint `/projections`

## 0.4.0

- feat: Limit the size of `nb_days` in `find_all_jobs_by_user`
- feat: implement anonymization, metrics and report generation as a batch
- feat: apply license check only during anonymization, not during upload
- fix: Prevent user from uploaded a dataframe with `bool` dtype
- fix: Correctly handle error on missing job
- fix: standardize metrics in the anonymization report

### BREAKING CHANGE

- remove `patch` parameter from `create_dataset`

## 0.3.3

- Add `should_stream` parameter to `{upload,download}_dataframe` and `{create,download}_dataset`.
  This should prevent issues with timeouts during upload and download, as well as lessen the load on the server for big files.
- Add `jobs.cancel_job` method to cancel a job
- Add `use_categorical_reduction` parameter
- Add maximum password length of 128 characters
- Add report creation without avatarization job
- Remove re-raise of JSONDecodeError
- Add commit hash to generated files
- Fix: verify that `known_variables` and `target` are known when launching a privacy metrics job
- Fix: call analyze_dataset only once in notebooks

## 0.3.2

- catch JSONDecodeError and re-raise with more info

## 0.3.1

- add `should_verify_ssl` to allow usage of self-signed certificate on server side
- add `InterRecordCumulatedDifferenceProcessor`
- add `InterRecordRangeDifferenceProcessor`
- improve logging and error handling in avatarization_pipeline to resume easier on failure

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
