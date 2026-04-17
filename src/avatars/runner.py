import os
import time
import warnings
import webbrowser
from dataclasses import asdict
from logging import getLogger
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
import tenacity
from avatar_yaml import (
    AvatarizationFastDPParameters,
    AvatarizationOpenDPParameters,
    AvatarizationParameters,
    PrivacyMetricsParameters,
)
from avatar_yaml import Config as Config
from avatar_yaml.models.advice import AdviceType
from avatar_yaml.models.avatar_metadata import (
    DataRecipient,
    DataSubject,
    DataType,
    SensitivityLevel,
)
from avatar_yaml.models.parameters import (
    AlignmentMethod,
    AugmentationStrategy,
    AvatarizationProcessorParameters,
    ExcludeVariablesMethod,
    ImputeMethod,
    ProjectionType,
    ReportLanguage,
    ReportType,
)
from avatar_yaml.models.schema import ColumnType, LinkMethod, PseudonymizationColumnConfig
from IPython.display import HTML, display

from avatars import __version__
from avatars.client import ApiClient
from avatars.constants import (
    DEFAULT_DELAY_BETWEEN_CONSECUTIVE_JOBS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TYPE,
    ERROR_STATUSES,
    JOB_EXECUTION_ORDER,
    MATCHERS,
    RESULTS_TO_STORE,
    VOLUME_NAME,
    PlotKind,
    Results,
    TypeResults,
)
from avatars.crash_handler import register_runner
from avatars.file_downloader import FileDownloader
from avatars.job_launcher import JobLauncher
from avatars.metrics_summary import build_metrics_summary_df
from avatars.models import BulkDeleteRequest, BulkDeleteResponse, JobKind, JobResponse
from avatars.results_organizer import ResultsOrganizer

logger = getLogger(__name__)


class Runner:
    def __init__(
        self,
        api_client: ApiClient,
        display_name: str,
        seed: int | None = None,
        max_distribution_plots: int | None = None,
        pia_data_recipient: DataRecipient = DataRecipient.UNKNOWN,
        pia_data_type: DataType = DataType.UNKNOWN,
        pia_data_subject: DataSubject = DataSubject.UNKNOWN,
        pia_sensitivity_level: SensitivityLevel = SensitivityLevel.UNDEFINED,
        report_language: ReportLanguage = ReportLanguage.EN,
    ) -> None:
        self.client = api_client
        self.display_name = display_name
        self.set_name: str | None = None
        self.config = Config(
            set_name=self.display_name, seed=seed, max_distribution_plots=max_distribution_plots
        )
        self.file_downloader = FileDownloader(api_client)
        self.results: ResultsOrganizer = ResultsOrganizer()
        self.jobs = JobLauncher(api_client, self.config)
        self.results_urls: dict[str, dict[str, Any]] = {}
        self._has_results_missing_warning_issued: bool = False
        self.report_language = report_language

        annotations = {
            "client_type": "python",
            "client_version": __version__,
        }
        self.config.create_metadata(
            annotations,
            pia_datarecipient=pia_data_recipient,
            pia_datatype=pia_data_type,
            pia_datasubject=pia_data_subject,
            pia_sensitivitylevel=pia_sensitivity_level,
        )

        # Register this Runner instance for crash reporting
        register_runner(self)

    def add_annotations(self, annotations: dict[str, str]) -> None:
        """Add metadata annotations to the config.

        Parameters
        ----------
        annotations
            A dictionary of annotations to add to the metadata.
        """
        if self.config.avatar_metadata is None:
            self.config.create_metadata(annotations)
        else:
            current_annotations = self.config.avatar_metadata.annotations or {}
            current_annotations.update(annotations)
            self.config.create_metadata(current_annotations)

    def add_table(
        self,
        table_name: str,
        data: str | pd.DataFrame,
        primary_key: str | None = None,
        foreign_keys: list | None = None,
        time_series_time: str | None = None,
        types: dict[str, ColumnType] = {},
        individual_level: bool | None = None,
        avatar_data: str | pd.DataFrame | None = None,
    ):
        """Add a table to the config and upload the data in the server.

        Parameters
        ----------
        table_name
            The name of the table.
        data
            The data to add to the table. Can be a path to a file or a pandas DataFrame.
        primary_key
            The primary key of the table.
        foreign_keys
            Foreign keys of the table.
        time_series_time
            name of the time column in the table (time series case).
        types
            A dictionary of column types with the column name as the key and the type as the value.
        individual_level
            A boolean as true if the table is at individual level or not. An individual level table
            is a table where each row corresponds to an individual (ex: patient, customer, etc.).
            Default behavior is True.
        avatar_data
            The avatar table if there is one. Can be a path to a file or a pandas DataFrame.
        """
        file, avatar_file = self.upload_file(table_name, data, avatar_data)
        if isinstance(data, pd.DataFrame):
            types = self._get_types(data, types)

        if foreign_keys == [None]:
            foreign_keys = None

        self.config.create_table(
            table_name=table_name,
            original_volume=VOLUME_NAME,
            original_file=file,
            avatar_volume=VOLUME_NAME if avatar_data is not None else None,
            avatar_file=avatar_file,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            time_series_time=time_series_time,
            types=types,
            individual_level=individual_level,
        )

    def advise_parameters(self, table_name: str | None = None) -> None:
        """Fill the parameters set with the server recommendation.

        Parameters
        ----------
        table_name
            The name of the table. If None, all tables will be used.
        """
        self._setup_advice_config()
        if table_name:
            tables = [table_name]
        else:
            tables = list(self.config.tables.keys())
        self._create_advice_jobs(tables)
        self._apply_advice_parameters(tables)

    def _setup_advice_config(self) -> None:
        """Create advice config and upload resources to server."""
        self.config.create_advice(advisor_type=[AdviceType.PARAMETERS])
        yaml = self.config.get_yaml()
        resource_response = self.client.resources.put_resources(
            display_name=self.display_name,
            yaml_string=yaml,
        )
        # Update set_name with the actual UUID returned by the backend
        self.set_name = str(resource_response.set_name)

    def _create_advice_jobs(self, tables: list[str]) -> None:
        """Download advice results for the specified tables."""
        for table_name in tables:
            if self.results.advice.get(table_name) is None:
                # Only launch the advice job once, not per table
                # but relaunch it if a table didn't get advice yet
                if self.set_name is None:
                    raise ValueError("Set name is not set. Cannot launch advice job.")
                self.jobs.launch_job(JobKind.advice, self.set_name)
                job_name = self.jobs.get_parameters_name(JobKind.advice)
                self._download_specific_result(job_name, Results.ADVICE)

    def _apply_advice_parameters(self, tables: list[str]) -> None:
        """Apply the downloaded advice parameters to each table."""
        job_name = self.jobs.get_parameters_name(JobKind.advice)
        for table_name in tables:
            advise_parameters = self.results.get_results(table_name, Results.ADVICE, job_name)
            if not isinstance(advise_parameters, dict):
                raise ValueError("Expected advice parameters to be a dictionary")

            imputation_data: dict[str, Any] = {}
            if advise_parameters.get("imputation") is not None:
                imputation_result = advise_parameters.get("imputation")
                if isinstance(imputation_result, dict):
                    imputation_data = imputation_result

            imputation_method = None
            if imputation_data.get("method") is not None:
                imputation_method = ImputeMethod(imputation_data.get("method"))

            self.set_parameters(
                k=advise_parameters.get("k"),
                use_categorical_reduction=advise_parameters.get("use_categorical_reduction"),
                ncp=advise_parameters.get("ncp"),
                imputation_method=imputation_method,
                imputation_k=imputation_data.get("k"),
                imputation_training_fraction=imputation_data.get("training_fraction"),
                imputation_return_data_imputed=imputation_data.get("return_data_imputed", False),
                table_name=table_name,
            )

    def upload_file(
        self,
        table_name: str,
        data: str | pd.DataFrame,
        avatar_data: str | pd.DataFrame | None = None,
    ):
        """Upload a file to the server.

        Parameters
        ----------
        data
            The data to upload. Can be a path to a file or a pandas DataFrame.
        file_name
            The name of the file.
        """
        extension = ".csv" if isinstance(data, pd.DataFrame) else Path(data).suffix
        file = table_name + extension
        self.client.upload_file(data=data, key=file)
        avatar_file = None
        if avatar_data is not None:
            avatar_file = table_name + "_avatars" + extension
            self.client.upload_file(data=avatar_data, key=avatar_file)
        return file, avatar_file

    def _get_types(
        self, data: pd.DataFrame, types: dict[str, ColumnType] = {}
    ) -> dict[str, ColumnType]:
        dtypes = {}
        for column_name, _type in data.dtypes.items():
            column_name_str = str(column_name)
            if column_name_str in types:
                dtypes[column_name_str] = types[column_name_str]
            else:
                dtypes[column_name_str] = self._get_type_from_pandas(str(_type))
        return dtypes

    def _get_type_from_pandas(self, value: str) -> ColumnType:
        """Return our data type from pandas type."""
        for matcher, our_type in MATCHERS.items():
            if matcher.search(value):
                return our_type
        return DEFAULT_TYPE

    def add_link(
        self,
        parent_table_name: str,
        parent_field: str,
        child_table_name: str,
        child_field: str,
        method: LinkMethod = LinkMethod.LINEAR_SUM_ASSIGNMENT,
    ):
        """Add a table link to the config.

        Parameters
        ----------
        parent_table_name
            The name of the parent table.
        child_table_name
            The name of the child table.
        parent_field
            The parent link key field (primary key) in the parent table.
        child_field
            The child link key field (foreign key)in the child table.
        method
            The method to use for linking the tables. Defaults to "linear_sum_assignment".
        """
        self.config.create_link(
            parent_table_name, child_table_name, parent_field, child_field, method.value
        )

    def set_parameters(
        self,
        table_name: str,
        k: int | None = None,
        ncp: int | None = None,
        use_categorical_reduction: bool | None = None,
        column_weights: dict[str, float] | None = None,
        exclude_variable_names: list[str] | None = None,
        exclude_replacement_strategy: ExcludeVariablesMethod | None = None,  # DEPRECATED
        exclude_variable_method: ExcludeVariablesMethod | None = None,
        imputation_method: ImputeMethod | None = None,
        imputation_k: int | None = None,
        imputation_training_fraction: float | None = None,
        imputation_return_data_imputed: bool | None = None,
        open_dp_epsilon: float | None = None,
        fast_dp_epsilon: float | None = None,
        time_series_nf: int | None = None,
        time_series_projection_type: ProjectionType | None = None,
        time_series_nb_points: int | None = None,
        time_series_method: AlignmentMethod | None = None,
        known_variables: list[str] | None = None,
        target: str | None = None,
        quantile_threshold: int | None = None,
        data_augmentation_strategy: float | AugmentationStrategy | dict[str, float] | None = None,
        data_augmentation_target_column: str | None = None,
        data_augmentation_should_anonymize_original_table: bool | None = None,
        processors: list[AvatarizationProcessorParameters] | None = None,
        pseudonymized_columns: dict[str, PseudonymizationColumnConfig] | None = None,
        use_excluded_variables_in_metrics: bool = False,
    ):
        """Set the parameters for a given table.

        This will overwrite any existing parameters for the table, including parameters set using
        `advise_parameter()`.

        Parameters
        ----------
        table_name
            The name of the table.
        k
            Number of nearest neighbors to consider for KNN-based methods.
        ncp
            Number of dimensions to consider for the KNN algorithm.
        use_categorical_reduction
            Whether to transform categorical variables into a
            latent numerical space before projection.
        column_weights
            Dictionary mapping column names to their respective weights,
            indicating the importance of each variable during the projection process.
        exclude_variable_names
            List of variable names to exclude from the projection.
        exclude_replacement_strategy:
            DEPRECATED: use exclude_variable_method instead.
        exclude_variable_method:
            Strategy for replacing excluded variables. Options: ROW_ORDER, COORDINATE_SIMILARITY.
        imputation_method
            Method for imputing missing values. Options: ``ImputeMethod.KNN``,
            ``ImputeMethod.MODE``, ``ImputeMethod.MEDIAN``, ``ImputeMethod.MEAN``,
            ``ImputeMethod.FAST_KNN``.
        imputation_k
            Number of neighbors to use for imputation if the method is KNN or FAST_KNN.
        imputation_training_fraction
            Fraction of the dataset to use for training the imputation model
            when using KNN or FAST_KNN.
        imputation_return_data_imputed:
            Whether to return the data with imputed values.
        open_dp_epsilon
            Epsilon value for differential privacy using OpenDP implementation.
        fast_dp_epsilon
            Epsilon value for fastDP avatarization.
        time_series_nf
            In time series context, number of degrees of freedom to
            retain in time series projections.
        time_series_projection_type
            In time series context, type of projection for time series. Options:
            ``ProjectionType.FCPA`` (default) or ``ProjectionType.FLATTEN``.
        time_series_method
            In time series context, method for aligning series. Options:
            ``AlignmentMethod.SPECIFIED``, ``AlignmentMethod.MAX``,
            ``AlignmentMethod.MIN``, ``AlignmentMethod.MEAN``.
        time_series_nb_points
            In time series context, number of points to generate for time series.
        known_variables
            List of known variables to be used for privacy metrics.
            These are variables that could be easily known by an attacker.
        target
            Target variable to predict, used for signal metrics.
        quantile_threshold
            Quantile threshold for privacy metrics calculations.
        data_augmentation_strategy
            Strategy for data augmentation. Can be a float representing the
            augmentation ratio, an AugmentationStrategy enum, or a dictionary
            mapping modality to their respective augmentation ratios.
        data_augmentation_target_column
            Target column for data augmentation when using a dictionary strategy or
            AugmentationStrategy.
        data_augmentation_should_anonymize_original_table
            SENSITIVE: Whether to anonymize the original table during data augmentation.
            Default is True.
        processors
            List of processor parameter objects (subclasses of AvatarizationProcessorParameters).
            Supports InterRecordRangeDifferenceParameters and RelativeDifferenceParameters.
            The order of the list determines the order in which processors are applied
            during preprocessing (and reversed during postprocessing).

            The transformations are transparent to the user - input and output have the same
            column structure at the end.
        pseudonymized_columns
            A mapping of column name to ``PseudonymizationColumnConfig`` describing the PII type
            and pseudonymization strategy to apply to each column. Only columns that should be
            pseudonymized need to be listed. Foreign key columns in child tables automatically
            inherit the pseudonymization mapping of the referenced parent primary key — no explicit
            configuration is needed on child FK columns.
        use_excluded_variables_in_metrics
            When True, excluded variables are NOT passed to metrics parameters,
            allowing privacy and signal metrics to include them in calculations.
            When False (default), excluded variables are also excluded from metrics calculations.
        """
        imputation = imputation_method.value if imputation_method else None
        if exclude_variable_method:
            replacement_strategy = exclude_variable_method.value
        elif exclude_replacement_strategy:
            warnings.warn(
                "The 'exclude_replacement_strategy' parameter is deprecated and will be removed "
                "in a future release. Please use 'exclude_variable_method' instead."
            )
            replacement_strategy = exclude_replacement_strategy.value
        else:
            replacement_strategy = None
        if k and open_dp_epsilon:
            raise ValueError(
                "Expected either k or open_dp_epsilon to be set, not both. "
                "If you want to use OpenDP avatarization, set open_dp_epsilon and remove k."
            )
        if k and fast_dp_epsilon:
            raise ValueError(
                "Expected either k or fast_dp_epsilon to be set, not both. "
                "If you want to use fastDP avatarization, set fast_dp_epsilon and remove k."
            )
        if open_dp_epsilon and fast_dp_epsilon:
            raise ValueError(
                "Expected either open_dp_epsilon or fast_dp_epsilon to be set, not both. "
                "Choose either OpenDP (open_dp_epsilon) or FastDP (fast_dp_epsilon)."
            )
        if k == 2:
            warnings.warn(
                "You have set k = 2, which is the minimum allowed value. With such a low k, "
                "each synthesized record closely mirrors only 2 original records, "
                "significantly reducing privacy protection."
            )

        # reset the parameters if they were already set
        if self.config.avatarization and self.config.avatarization.get(table_name):
            del self.config.avatarization[table_name]
        avatarization_open_dp = getattr(self.config, "avatarization_open_dp", None)
        if avatarization_open_dp and avatarization_open_dp.get(table_name):
            del avatarization_open_dp[table_name]
        avatarization_fast_dp = getattr(self.config, "avatarization_fast_dp", None)
        if avatarization_fast_dp and avatarization_fast_dp.get(table_name):
            del avatarization_fast_dp[table_name]
        if self.config.privacy_metrics and self.config.privacy_metrics.get(table_name):
            del self.config.privacy_metrics[table_name]
        if self.config.signal_metrics and self.config.signal_metrics.get(table_name):
            del self.config.signal_metrics[table_name]
        if self.config.time_series and self.config.time_series.get(table_name):
            del self.config.time_series[table_name]
        if k:
            # Avatarizaztion with avatar method
            self.config.create_avatarization_parameters(
                table_name=table_name,
                k=k,
                ncp=ncp,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                imputation_return_data_imputed=imputation_return_data_imputed,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                data_augmentation_strategy=data_augmentation_strategy,
                data_augmentation_target_column=data_augmentation_target_column,
                data_augmentation_should_anonymize_original_table=data_augmentation_should_anonymize_original_table,
                avatarization_processors_parameters=processors,
                pseudonymized_columns=pseudonymized_columns,
            )

        elif open_dp_epsilon:
            # OpenDP avatarization (MST method)
            self.config.create_avatarization_open_dp_parameters(
                table_name=table_name,
                epsilon=open_dp_epsilon,
                ncp=ncp,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                imputation_return_data_imputed=imputation_return_data_imputed,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                data_augmentation_strategy=data_augmentation_strategy,
                data_augmentation_target_column=data_augmentation_target_column,
                data_augmentation_should_anonymize_original_table=data_augmentation_should_anonymize_original_table,
                avatarization_processors_parameters=processors,
                pseudonymized_columns=pseudonymized_columns,
            )

        elif fast_dp_epsilon:
            # FastDP avatarization (DP mechanisms in latent space)
            self.config.create_avatarization_fast_dp_parameters(
                table_name=table_name,
                epsilon=fast_dp_epsilon,
                ncp=ncp,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                imputation_return_data_imputed=imputation_return_data_imputed,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                data_augmentation_strategy=data_augmentation_strategy,
                data_augmentation_target_column=data_augmentation_target_column,
                data_augmentation_should_anonymize_original_table=data_augmentation_should_anonymize_original_table,
                avatarization_processors_parameters=processors,
                pseudonymized_columns=pseudonymized_columns,
            )

        if (
            time_series_nf
            or time_series_projection_type
            or time_series_nb_points
            or time_series_method
        ):
            method = time_series_method.value if time_series_method else None
            projection_type = (
                time_series_projection_type.value if time_series_projection_type else None
            )
            self.config.create_time_series_parameters(
                table_name=table_name,
                nf=time_series_nf,
                projection_type=projection_type,
                nb_points=time_series_nb_points,
                method=method,
            )

        metrics_exclude_variable_names = (
            None if use_excluded_variables_in_metrics else exclude_variable_names
        )
        metrics_replacement_strategy = (
            None if use_excluded_variables_in_metrics else replacement_strategy
        )

        self.config.create_privacy_metrics_parameters(
            table_name=table_name,
            ncp=ncp,
            use_categorical_reduction=use_categorical_reduction,
            imputation_method=imputation,
            imputation_k=imputation_k,
            imputation_training_fraction=imputation_training_fraction,
            imputation_return_data_imputed=imputation_return_data_imputed,
            exclude_variable_names=metrics_exclude_variable_names,
            exclude_variable_method=metrics_replacement_strategy,
            known_variables=known_variables,
            target=target,
            quantile_threshold=quantile_threshold,
            column_weights=column_weights,
        )

        self.config.create_signal_metrics_parameters(
            table_name=table_name,
            ncp=ncp,
            use_categorical_reduction=use_categorical_reduction,
            imputation_method=imputation,
            imputation_k=imputation_k,
            imputation_training_fraction=imputation_training_fraction,
            imputation_return_data_imputed=imputation_return_data_imputed,
            exclude_variable_names=metrics_exclude_variable_names,
            exclude_variable_method=metrics_replacement_strategy,
            column_weights=column_weights,
        )

    def update_parameters(self, table_name: str, **kwargs) -> None:
        """
        Update specific parameters for the table while preserving other existing parameters.
        Only updates the parameters that are provided, keeping existing values for others.

        Parameters
        ----------
        table_name
            The name of the table.
        **kwargs
            The parameters to update. Only parameters that are provided will be updated.
            See set_parameters for the full list of available parameters.
        """
        avatarization = getattr(self.config, "avatarization", None)
        avatarization_open_dp = getattr(self.config, "avatarization_open_dp", None)
        avatarization_fast_dp = getattr(self.config, "avatarization_fast_dp", None)
        if (
            (avatarization.get(table_name) if avatarization else None) is None
            and (avatarization_open_dp.get(table_name) if avatarization_open_dp else None) is None
            and (avatarization_fast_dp.get(table_name) if avatarization_fast_dp else None) is None
        ):
            raise ValueError(
                f"No existing parameters found for table '{table_name}'. "
                "Use set_parameters to create new parameters."
            )
        # Get current parameters for this table
        current_params = self._extract_current_parameters(table_name)

        # Update only the parameters that were provided
        for param_name, param_value in kwargs.items():
            current_params[param_name] = param_value
        # Apply all parameters back using set_parameters
        self.set_parameters(table_name=table_name, **current_params)

    def _extract_current_parameters(self, table_name: str) -> dict:
        """Extract the current parameters for a given table.

        Parameters
        ----------
        table_name
            The name of the table.

        Returns
        -------
        dict
            A dictionary containing the current parameters for
            the table as it is used in set_parameters.
        """

        current_params: dict[str, Any] = {}

        # Extract avatarization parameters
        if (
            self.config.avatarization is not None
            and table_name in self.config.avatarization.keys()
        ):
            # Standard avatarization parameters
            params: Optional[
                Union[
                    AvatarizationParameters,
                    AvatarizationOpenDPParameters,
                    AvatarizationFastDPParameters,
                    PrivacyMetricsParameters,
                ]
            ] = self.config.avatarization[table_name]
            if isinstance(params, AvatarizationParameters):
                current_params.update(
                    {
                        "k": params.k,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))
        elif (
            hasattr(self.config, "avatarization_open_dp")
            and self.config.avatarization_open_dp is not None
            and table_name in self.config.avatarization_open_dp.keys()
        ):
            # OpenDP avatarization parameters (end-to-end DP)
            params = self.config.avatarization_open_dp[table_name]
            if isinstance(params, AvatarizationOpenDPParameters):
                current_params.update(
                    {
                        "open_dp_epsilon": params.epsilon if params.epsilon else None,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))
        elif (
            hasattr(self.config, "avatarization_fast_dp")
            and self.config.avatarization_fast_dp is not None
            and table_name in self.config.avatarization_fast_dp.keys()
        ):
            # FastDP avatarization parameters
            # Only epsilon is exposed; mechanism-specific params use defaults
            params = self.config.avatarization_fast_dp[table_name]
            if isinstance(params, AvatarizationFastDPParameters):
                current_params.update(
                    {
                        "fast_dp_epsilon": params.epsilon if params.epsilon else None,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))
        else:
            params = None  # No parameters has been preset

        if (
            self.config.privacy_metrics is not None
            and self.config.privacy_metrics.get(table_name) is not None
        ):
            params = self.config.privacy_metrics[table_name]
            current_params.update(
                {
                    "use_categorical_reduction": params.use_categorical_reduction,
                    "ncp": params.ncp,
                }
            )
        else:
            params = None  # No parameters has been preset

        # Extract imputation parameters
        if params and params.imputation:
            current_params.update(
                {
                    "imputation_method": ImputeMethod(params.imputation["method"])
                    if params.imputation["method"]
                    else None,
                    "imputation_k": params.imputation["k"] if params.imputation["k"] else None,
                    "imputation_training_fraction": params.imputation["training_fraction"]
                    if params.imputation["training_fraction"]
                    else None,
                    "imputation_return_data_imputed": params.imputation["return_data_imputed"],
                }
            )

        # Extract time series parameters
        if self.config.time_series and table_name in self.config.time_series.keys():
            ts_params = self.config.time_series[table_name]

            # Projection parameters
            if ts_params.projection:
                current_params.update(
                    {
                        "time_series_nf": ts_params.projection["nf"]
                        if ts_params.projection["nf"]
                        else None,
                        "time_series_projection_type": ProjectionType(
                            ts_params.projection["projection_type"]
                        )
                        if ts_params.projection["projection_type"]
                        else None,
                    }
                )

            # Alignment parameters
            if ts_params.alignment:
                current_params.update(
                    {
                        "time_series_nb_points": ts_params.alignment["nb_points"]
                        if ts_params.alignment["nb_points"]
                        else None,
                        "time_series_method": AlignmentMethod(ts_params.alignment["method"])
                        if ts_params.alignment["method"]
                        else None,
                    }
                )

        # Extract privacy metrics parameters
        if (
            self.config.privacy_metrics is not None
            and table_name in self.config.privacy_metrics.keys()
        ):
            pm_params = self.config.privacy_metrics[table_name]
            to_update = {
                "known_variables": pm_params.known_variables,
                "target": pm_params.target,
                "quantile_threshold": pm_params.quantile_threshold,
            }
            current_params.update(to_update)

            # Detect use_excluded_variables_in_metrics: True when avatarization has
            # exclude_variables but privacy metrics does not.
            avatarization_has_excluded = bool(current_params.get("exclude_variable_names"))
            metrics_has_excluded = bool(
                pm_params.exclude_variables and pm_params.exclude_variables.get("variable_names")
            )
            if avatarization_has_excluded and not metrics_has_excluded:
                current_params["use_excluded_variables_in_metrics"] = True

        return current_params

    def _extract_exclude_parameters(self, params) -> dict:
        """Extract exclude variables parameters from parameter object.

        Parameters
        ----------
        params:
            The parameters object that contains exclude_variables information.

        Returns
        -------
        A dictionary containing exclude_variable_names and exclude_variable_method parameters.
        """
        result = {}
        if params.exclude_variables:
            result["exclude_variable_names"] = (
                params.exclude_variables["variable_names"]
                if params.exclude_variables["variable_names"]
                else None
            )
            result["exclude_variable_method"] = (
                ExcludeVariablesMethod(params.exclude_variables["replacement_strategy"])
                if params.exclude_variables["replacement_strategy"]
                else None
            )
        return result

    def delete_parameters(self, table_name: str, parameters_names: list[str] | None = None):
        """Delete parameters from the config.

        Parameters
        ----------
        table_name
            The name of the table.
        parameters_names
            The names of the parameters to delete. If None, all parameters will be deleted.
        """
        self.config.delete_parameters(table_name, parameters_names)

    def delete_link(self, parent_table_name: str, child_table_name: str):
        """Delete a link from the config.

        Parameters
        ----------
        parent_table_name
            The name of the parent table.
        child_table_name
            The name of the child table.
        """
        self.config.delete_link(parent_table_name, child_table_name)

    def delete_table(self, table_name: str):
        """Delete a table from the config.

        Parameters
        ----------
        table_name
            The name of the table.
        """
        self.config.delete_table(table_name)

    def get_yaml(self, path: str | None = None):
        """Get the yaml config.

        Parameters
        ----------
        path
            The path to the yaml file. If None, the default config will be returned.
        """
        return self.config.get_yaml(path)

    def _handle_existing_results(self, ignore_warnings: bool = False) -> None:
        """Warn and clean up local state when re-running a runner that already has results."""
        advice_job_name = self.jobs.get_parameters_name(JobKind.advice)
        has_run_before = (
            not self.results.is_results_empty()
            or any(key != advice_job_name for key in self.results_urls)
            or any(job != advice_job_name for job in self.jobs.get_launched_jobs())
        )

        if has_run_before:
            if not ignore_warnings:
                set_name = self.set_name
                warnings.warn(
                    f"\nThis runner already has results for set_name '{set_name}'.\n"
                    "Re-running will create a new set_name — previous results will no longer "
                    "be accessible from this runner.\n"
                    f"To access previous results later:\n"
                    f"regenerated_runner = manager.create_runner_from_id('{set_name}')\n"
                    "regenerated_runner.shuffled(...)",
                    UserWarning,
                )
            self.results_urls.clear()
            self.results = ResultsOrganizer()
            self.jobs.jobs.clear()

    def run(self, jobs_to_run: list[JobKind] = JOB_EXECUTION_ORDER, ignore_warnings: bool = False):
        """Run avatarization jobs.

        This method creates resources and launches the specified jobs in the correct order.
        If this runner has existing results from a previous run, a ``UserWarning`` is emitted
        with the old ``set_name`` so you can recover previous results if needed. Local state
        is then cleared and a new run starts.

        Parameters
        ----------
        jobs_to_run : list[JobKind]
            List of job types to run. Defaults to all jobs in execution order.
        ignore_warnings: bool
            Whether to ignore warnings about existing results when re-running a runner.
            Defaults to False.

        Examples
        --------
        >>> runner = manager.create_runner("my_dataset")
        >>> runner.add_table("customers", data=df)
        >>> runner.run()
        >>>
        >>> # Running again emits a UserWarning with the old set_name, then proceeds
        >>> runner.run()
        """
        self._handle_existing_results(ignore_warnings=ignore_warnings)

        # Create report configurations if report job is requested and report configurations
        # are not already set (could happen when creating a runner from an existing config)
        if JobKind.report in jobs_to_run:
            if self.config.report is None or ReportType.BASIC not in self.config.report:
                self.config.create_report(language=self.report_language)
            if self.config.report is None or ReportType.PIA not in self.config.report:
                self.config.create_report(ReportType.PIA, language=self.report_language)

        yaml = self.get_yaml()

        resource_response = self.client.resources.put_resources(
            display_name=self.display_name,
            yaml_string=yaml,
        )
        # Update set_name with the actual UUID returned by the backend
        self.set_name = str(resource_response.set_name)
        self.jobs.set_name = self.set_name

        # Execute jobs in order
        jobs_to_run = sorted(jobs_to_run, key=lambda job: JOB_EXECUTION_ORDER.index(job))

        for i, job_kind in enumerate(jobs_to_run):
            # Add small delay between job creations to avoid bursts in api calls
            # Skip delay for first job
            if i > 0:
                time.sleep(DEFAULT_DELAY_BETWEEN_CONSECUTIVE_JOBS)
            self.jobs.launch_job(job_kind, self.set_name)

    def get_job(self, job_name: JobKind | str) -> JobResponse:
        """
        Get the job by name.

        Parameters
        ----------
        job_name
            The name of the job to get.
        """
        return self.jobs.get_job_status(job_name)

    def get_status(self, job_name: JobKind):
        """
        Get the status of a job by name.
        Parameters
        ----------
        job_name
            The name of the job to get.
        """
        return self.get_job(job_name).status

    def delete(
        self, job_names: JobKind | str | list[JobKind | str] | None = None
    ) -> BulkDeleteResponse:
        """Delete one or more jobs launched by this runner.

        When called without arguments, every job launched by this runner is deleted.

        Parameters
        ----------
        job_names
            A single job kind/name, a list of job kinds/names, or ``None`` to
            delete all launched jobs.

        Returns
        -------
        BulkDeleteResponse
            Response containing deleted and failed jobs.

        Examples
        --------
        >>> runner.delete()                                              # all jobs
        >>> runner.delete(JobKind.standard)                             # single job
        >>> runner.delete([JobKind.standard, JobKind.privacy_metrics])  # multiple jobs
        """
        if job_names is None:
            names: list[JobKind | str] = list(self.jobs.get_launched_jobs())
        elif not isinstance(job_names, list):
            names = [job_names]
        else:
            names = job_names
        job_ids = [self.jobs.get_job_id(name) for name in names]
        return self.client.jobs.bulk_delete_jobs(BulkDeleteRequest(job_names=job_ids))

    def _retrieve_job_result_urls(self, job_name: str) -> None:
        """
        Get the result of a job by name.

        Parameters
        ----------
        job_name
            The name of the job to get.
        """

        def check_job_status() -> JobResponse:
            """Check job status and raise if in error state, otherwise return if not done."""
            job = self.get_job(job_name)

            if job.status in ERROR_STATUSES:
                if job.exception:
                    raise ValueError(f"Job {job_name} failed with exception: {job.exception}")
                raise ValueError("internal error")

            if not job.done:
                # Raise to trigger retry
                raise tenacity.TryAgain

            return job

        # Use tenacity to poll with exponential backoff capped at 20s
        # Starts at 5s, 20% longer every time, maxes out at 20s
        for attempt in tenacity.Retrying(
            wait=tenacity.wait_exponential(
                min=DEFAULT_POLL_INTERVAL,
                max=4 * DEFAULT_POLL_INTERVAL,
                exp_base=1.2,
            ),
            retry=tenacity.retry_if_exception_type(tenacity.TryAgain),
            reraise=True,
        ):
            with attempt:
                check_job_status()

        job_id = self.jobs.get_job_id(job_name)
        self.results_urls[job_name] = self.client.results.get_results(job_id)

    def _populate_results_from_existing_jobs(self) -> None:
        """Fetch and populate results URLs from all completed jobs for this set_name.

        This method is used when reconstructing a Runner from an existing set_name.
        It fetches all jobs associated with the set_name and populates the results_urls
        dictionary for completed jobs only. It also registers these jobs with the
        JobLauncher so they can be accessed via normal result methods.

        If a job's results are no longer available on the server (404 error), a warning
        is issued but the method continues to process other jobs.
        """
        if not self.set_name:
            return

        all_jobs = self.client.jobs.get_jobs()

        # Filter jobs by set_name and only include completed jobs
        for job in all_jobs.jobs:
            if str(job.set_name) == self.set_name and job.done and not job.exception:
                job_name = job.name
                parameters_name = job.parameters_name
                try:
                    self.results_urls[parameters_name] = self.client.results.get_results(job_name)

                    self.jobs.register_existing_job(parameters_name, job_name, f"/jobs/{job_name}")

                except Exception as e:
                    # Keep backward-compatible behavior only for missing-results 404s.
                    error_message = str(e).lower()
                    is_missing_results_404 = (
                        "error status 404" in error_message
                        and "results file for job" in error_message
                    )
                    if is_missing_results_404:
                        if not self._has_results_missing_warning_issued:
                            tables_list = list(self.config.tables.keys())
                            warnings.warn(
                                f"Results for job '{job_name}' are no longer "
                                "available on the server. "
                                "Input data has also been cleaned up. "
                                f"You need to reupload the following tables: {tables_list}. "
                                "You can relaunch the job with the same configuration by calling "
                                "runner.run() after re-uploading your data with "
                                "runner.upload_file().",
                            )
                            # raise only once if multiple jobs are missing results
                            self._has_results_missing_warning_issued = True
                        continue

                    raise

    def get_specific_result_urls(
        self,
        job_name: str,
        result: Results = Results.SHUFFLED,
    ) -> list[str]:
        if not self.jobs.has_job(job_name):
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        if job_name not in self.results_urls:
            self._retrieve_job_result_urls(job_name)
        if result not in self.results_urls[job_name]:
            return []
        return self.results_urls[job_name][result]

    def _download_all_files(self):
        for job_name in self.jobs.get_launched_jobs():
            if not self.results_urls or job_name not in self.results_urls.keys():
                self._retrieve_job_result_urls(job_name)
            for result in self.results_urls[job_name].keys():
                for table_name in self.config.tables.keys():
                    if result in Results:
                        if Results(result) in RESULTS_TO_STORE:
                            self.get_specific_result(table_name, job_name, Results(result))

    def _download_specific_result(
        self,
        job_name: str,
        result_name: Results,
    ) -> None:
        urls = self.get_specific_result_urls(job_name=job_name, result=result_name)
        # Use batch download to get all file credentials at once
        downloaded_results = self.file_downloader.download_files_batch(urls)
        for url, result in downloaded_results.items():
            metadata = self._get_metadata(url, result_name, job_name)
            table_name = self.results.get_table_name(result_name, url, result, metadata)
            if table_name is not None:
                self.results.set_results(
                    table_name=table_name,
                    result=result,
                    result_name=result_name,
                    metadata=metadata,
                )

    def _get_metadata(
        self, url: str, result_name: Results, job_name: str
    ) -> dict[str, Any] | None:
        match result_name:
            case Results.FIGURES:
                return self._get_figure_metadata(url, job_name)
            case Results.METADATA:
                return {"kind": job_name}
            case _:
                return None

    def _get_figure_metadata(self, url: str, job_name: str) -> dict[str, Any] | None:
        figures_metadatas = self.file_downloader.download_file(
            self.results_urls[job_name][Results.FIGURES_METADATA][0]
        )
        if isinstance(figures_metadatas, list):
            return self.results.find_figure_metadata(figures_metadatas, url)
        else:
            raise TypeError(
                f"Expected a list, got {type(figures_metadatas)} instead for {url} metadata."
            )

    def get_specific_result(
        self,
        table_name: str,
        job_name: JobKind,
        result: Results = Results.SHUFFLED,
    ) -> TypeResults:
        job_name_str = self.jobs.get_parameters_name(job_name)
        if table_name not in self.config.tables.keys():
            raise ValueError(f"Expected table '{table_name}' to be created.")
        if not self.jobs.has_job(job_name_str):
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        if self.results.get_results(table_name, result, job_name_str) is None:
            self._download_specific_result(job_name_str, result)
        return self.results.get_results(table_name, result, job_name_str)

    def get_all_results(self):
        """
        Get all results.

        Returns
        -------
        dict
            A dictionary with the results of each job on every table.
        Each job is a dictionary with the table name as key and the results as value.
        The results are a dictionary with the result name as key and the data as value.
        The data can be a pandas DataFrame or a dictionary depending on the result type.
        """
        self._download_all_files()
        return self.results

    def download_report(self, path: str | None = None, report_type: ReportType = ReportType.BASIC):
        """
        Download the report.

        Parameters
        ----------
        path
            The path to save the report. For a single report this is used as-is.
            When multiple PIA reports are returned (one per table), an index
            prefix is added to the filename only: ``dir/0_report.pdf``,
            ``dir/1_report.pdf``, etc.
        """
        is_pia = report_type == ReportType.PIA
        job_name = self.jobs.get_parameters_name(JobKind.report, pia_report=is_pia)
        if self.results_urls.get(job_name) is None:
            self._retrieve_job_result_urls(job_name)
        urls = self.results_urls[job_name][Results.REPORT]
        is_multi = len(urls) > 1
        for i, url in enumerate(urls):
            if path is not None:
                if is_multi:
                    p = Path(path)
                    output_path = str(p.parent / f"{i}_{p.name}")
                else:
                    output_path = path
            else:
                output_path = Path(url).name
            self.file_downloader.download_file(url, path=output_path)

    def print_parameters(self, table_name: str | None = None) -> None:
        """Print the parameters for a table.

        Parameters
        ----------
        table_name
            The name of the table.
            If None, all parameters will be printed.
        """
        if table_name is None:
            for table_name in self.config.tables.keys():
                self.print_parameters(table_name)
            return
        if table_name not in self.config.tables.keys():
            raise ValueError(f"Expected table '{table_name}' to be created. Try running it first.")

        # Print avatarization parameters
        avatarization_open_dp = getattr(self.config, "avatarization_open_dp", None)
        avatarization_fast_dp = getattr(self.config, "avatarization_fast_dp", None)
        if self.config.avatarization and table_name in self.config.avatarization:
            print(f"--- Avatarization parameters for {table_name}: ---")  # noqa: T201
            print(asdict(self.config.avatarization[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        elif avatarization_open_dp and table_name in avatarization_open_dp:
            print(f"--- Avatarization OpenDP parameters for {table_name}: ---")  # noqa: T201
            print(asdict(avatarization_open_dp[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        elif avatarization_fast_dp and table_name in avatarization_fast_dp:
            print(f"--- Avatarization FastDP parameters for {table_name}: ---")  # noqa: T201
            print(asdict(avatarization_fast_dp[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        else:
            print(f"--- No avatarization parameters set for {table_name} ---")  # noqa: T201
            print("\n")  # noqa: T201

        # Print privacy metrics parameters
        if self.config.privacy_metrics and table_name in self.config.privacy_metrics:
            print(f"--- Privacy metrics for {table_name}: ---")  # noqa: T201
            print(asdict(self.config.privacy_metrics[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        else:
            print(f"--- No privacy metrics parameters set for {table_name} ---")  # noqa: T201
            print("\n")  # noqa: T201

        # Print signal metrics parameters
        if self.config.signal_metrics and table_name in self.config.signal_metrics:
            print(f"--- Signal metrics for {table_name}: ---")  # noqa: T201
            print(asdict(self.config.signal_metrics[table_name]))  # noqa: T201
        else:
            print(f"--- No signal metrics parameters set for {table_name} ---")  # noqa: T201

    def kill(self):
        """Method not implemented yet."""
        pass

    def shuffled(self, table_name: str) -> pd.DataFrame:
        """
        Get the shuffled data.

        Parameters
        ----------
        table_name
            The name of the table to get the shuffled data from.

        Returns
        -------
        pd.DataFrame
            The shuffled data as a pandas DataFrame.
        """
        shuffled = self.get_specific_result(table_name, JobKind.standard, Results.SHUFFLED)
        if not isinstance(shuffled, pd.DataFrame):
            raise TypeError(f"Expected a pd.DataFrame, got {type(shuffled)} instead.")
        return shuffled

    def sensitive_unshuffled(self, table_name: str) -> pd.DataFrame:
        """
        Get the unshuffled data.
        This is sensitive data and should be used with caution.

        Parameters
        ----------
        table_name
            The name of the table to get the unshuffled data from.

        Returns
        -------
        pd.DataFrame
            The unshuffled data as a pandas DataFrame.
        """
        unshuffled = self.get_specific_result(table_name, JobKind.standard, Results.UNSHUFFLED)
        if not isinstance(unshuffled, pd.DataFrame):
            raise TypeError(f"Expected a pd.DataFrame, got {type(unshuffled)} instead.")
        return unshuffled

    def privacy_metrics(self, table_name: str) -> list[dict]:
        """
        Get the privacy metrics.

        Parameters
        ----------
        table_name
            The name of the table to get the privacy metrics from.

        Returns
        -------
        dict
            The privacy metrics as a list of dictionary.
        """
        results = self.get_specific_result(
            table_name, JobKind.privacy_metrics, Results.PRIVACY_METRICS
        )
        if not isinstance(results, list):
            raise TypeError(f"Expected a list, got {type(results)} instead.")
        return results

    def signal_metrics(self, table_name: str) -> list[dict]:
        """
        Get the signal metrics.

        Parameters
        ----------
        table_name
            The name of the table to get the signal metrics from.

        Returns
        -------
        dict
            The signal metrics as a list of dictionary.
        """
        results = self.get_specific_result(
            table_name, JobKind.signal_metrics, Results.SIGNAL_METRICS
        )
        if not isinstance(results, list):
            raise TypeError(f"Expected a list, got {type(results)} instead.")
        return results

    def render_privacy_metrics_summary(
        self,
        open_in_browser: bool = False,  # DEPRECATED
    ) -> dict:
        """Get the aggregated privacy metrics summary across tables.

        Only available for multi-table jobs.
        Parameters
        ----------
        open_in_browser
            Whether to save the summary to a file and open it in a browser. deprecated and will be
            removed in the future, as the summary is now returned as a dict instead of an HTML file

        Returns
        -------
        dict
            A nested dict ``{table_name: {reference: meta_metric}}``.
        """
        if len(self.config.tables) <= 1:
            raise ValueError(
                "render_privacy_metrics_summary is only available for multi-table jobs."
            )
        if (
            self.results.get_results("summary", Results.PRIVACY_METRICS_SUMMARY, "privacy_metrics")
            is None
        ):
            self._download_specific_result("privacy_metrics", Results.PRIVACY_METRICS_SUMMARY)
        results = self.results.get_results(
            "summary", Results.PRIVACY_METRICS_SUMMARY, "privacy_metrics"
        )
        if not isinstance(results, dict):
            raise TypeError(f"Expected a dict, got {type(results)} instead.")
        return results

    def render_signal_metrics_summary(self) -> dict:
        """Get the aggregated signal metrics summary across tables.

        Only available for multi-table jobs.

        Returns
        -------
        dict
            A nested dict ``{table_name: {reference: meta_metric}}``.
        """
        if len(self.config.tables) <= 1:
            raise ValueError(
                "render_signal_metrics_summary is only available for multi-table jobs."
            )
        if self.results.get_results("summary", Results.SIGNAL_METRICS_SUMMARY, "") is None:
            self._download_specific_result("signal_metrics", Results.SIGNAL_METRICS_SUMMARY)
        results = self.results.get_results("summary", Results.SIGNAL_METRICS_SUMMARY, "")
        if not isinstance(results, dict):
            raise TypeError(f"Expected a dict, got {type(results)} instead.")
        return results

    def metrics_summary(self) -> pd.DataFrame:
        """Get the combined privacy and signal metrics summary across tables as a DataFrame.

        Only available for multi-table jobs.

        Returns
        -------
        pd.DataFrame
            A DataFrame indexed by ``table_name`` with MultiIndex columns ``(reference, metric)``
            where ``reference`` is the top level and ``metric`` is ``privacy`` or ``signal``,
            combining both meta-metrics for each table/reference pair.
        """
        return build_metrics_summary_df(
            privacy=self.render_privacy_metrics_summary(),
            signal=self.render_signal_metrics_summary(),
        )

    def render_plot(self, table_name: str, plot_kind: PlotKind, open_in_browser: bool = False):
        """
        Render a plot for a given table.
        The different plot kinds are defined in the PlotKind enum.

        Parameters
        ----------
        table_name
            The name of the table to get the plot from.
        plot_kind
            The kind of plot to render.
        open_in_browser
            Whether to save the plot to a file and open it in a browser.
        """
        results = self.get_specific_result(table_name, JobKind.standard, Results.FIGURES)
        if not isinstance(results, dict):
            raise TypeError(f"Expected a dict, got {type(results)} instead.")
        if plot_kind not in results:
            raise ValueError(f"No {plot_kind} found for table '{table_name}'.")
        plots = results[plot_kind]
        for idx, plot in enumerate(plots):
            filename = None
            if open_in_browser:
                filename = f"{table_name}_{plot_kind.value}_{idx}.html"
                self._save_file(plot, filename=filename)
            self._open_plot(plot, filename=filename)

    def projections(self, table_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get the projections.

        Parameters
        ----------
        table_name
            The name of the table to get the projections from.

        Returns
        -------
        pd.DataFrame
            The projections as a pandas DataFrame.
        """
        original_coordinates = self.get_specific_result(
            table_name, JobKind.standard, Results.PROJECTIONS_ORIGINAL
        )
        avatars_coordinates = self.get_specific_result(
            table_name, JobKind.standard, Results.PROJECTIONS_AVATARS
        )
        if not (
            isinstance(avatars_coordinates, pd.DataFrame)
            and isinstance(original_coordinates, pd.DataFrame)
        ):
            raise TypeError(
                "Expected a pd.DataFrame, "
                f"got {type(original_coordinates)} and {type(avatars_coordinates)} instead."
            )
        return original_coordinates, avatars_coordinates

    def table_summary(self, table_name: str) -> pd.DataFrame:
        """
        Get the table summary.

        Parameters
        ----------
        table_name
            The name of the table to get the summary from.

        Returns
        -------
        pd.DataFrame
            The table summary as a dataframe.
        """
        results = self.get_specific_result(table_name, JobKind.advice, Results.ADVICE)
        if not isinstance(results, dict) or "summary" not in results.keys():
            raise ValueError(f"Summary not found in results for table '{table_name}'")

        summary_data = results["summary"]
        if "stats" not in summary_data.keys():
            raise ValueError(f"Summary not found in results for table '{table_name}'")
        return pd.DataFrame(summary_data["stats"])

    def from_yaml(self, yaml_path: str) -> None:
        """Load configuration from a YAML file.

        This replaces the current runner's configuration with the one from the file.

        **Note**: Table data files are not automatically loaded. Use ``upload_file()``
        to provide data before running jobs.

        Parameters
        ----------
        yaml_path : str
            The path to the YAML configuration file.
        """
        with open(yaml_path, "r") as file:
            yaml_string = file.read()

        # Parse YAML using ConfigParser
        self.config = Config.from_yaml(yaml_string)

    def _open_plot(self, plot_html: HTML, filename: str | None = None):
        """Render a plot, optionally saving it and opening it in a browser."""
        if filename:
            file_path = os.path.abspath(filename)
            webbrowser.open(f"file://{file_path}")
        else:
            display(plot_html)

    def _save_file(self, file_content: HTML, filename: str | None = None):
        """Save the HTML file content to a specified path."""
        if filename is None:
            return None
        with open(filename, "w", encoding="utf-8") as file:
            file.write(file_content.data)
