import os
import secrets
import time
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
import yaml
from avatar_yaml import (
    AvatarizationDPParameters,
    AvatarizationParameters,
    PrivacyMetricsParameters,
)
from avatar_yaml import Config as Config
from avatar_yaml.models.parameters import (
    AlignmentMethod,
    ExcludeVariablesMethod,
    ImputeMethod,
    ProjectionType,
)
from avatar_yaml.models.schema import ColumnType, LinkMethod
from IPython.display import HTML, display

from avatars.client import ApiClient
from avatars.constants import (
    DEFAULT_RETRY_INTERVAL,
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
from avatars.file_downloader import FileDownloader
from avatars.models import JobCreateRequest, JobCreateResponse, JobKind, JobResponse
from avatars.results_organizer import ResultsOrganizer


class Runner:
    def __init__(self, api_client: ApiClient, set_name: str, seed: int | None = None) -> None:
        self.client = api_client
        self.set_name = self._get_valid_set_name(set_name)
        self.config = Config(set_name=self.set_name, seed=seed)
        self.jobs: dict[JobKind | str, JobCreateResponse] = {}
        self.results_urls: dict[JobKind, dict[str, list[str]]] = {}
        self.file_downloader = FileDownloader(api_client)
        self.results: ResultsOrganizer = ResultsOrganizer()

    def _get_valid_set_name(self, set_name: str) -> str:
        """Ensure the set name isn't already created."""
        return set_name + "_python_" + secrets.token_hex(4)

    def add_table(
        self,
        table_name: str,
        data: str | pd.DataFrame,
        primary_key: str | None = None,
        foreign_keys: list | None = None,
        time_series_time: str | None = None,
        types: dict[str, ColumnType] = {},
        individual_level: bool | None = None,
        avatar_data: str | None = None,
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
            is a table where each row corresponds to an individual (ex: patient, customer, etc.)
        avatar_data
            The avatar table if there is one. Can be a path to a file or a pandas DataFrame.
        """
        if self.config.results_volume is None:
            self.config.create_results_volume(
                url=self._get_url_results_volume(),
                result_volume_name=self._get_results_volume_name(),
            )

        file, avatar_file = self.upload_file(table_name, data, avatar_data)
        if isinstance(data, pd.DataFrame):
            types = self._get_types(data, types)

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
        yaml = self.config.get_advice_yaml(name=JobKind.advice.value)
        self.client.resources.put_resources(
            set_name=self.set_name,
            yaml_string=yaml,
        )
        if table_name:
            tables = [table_name]
        else:
            tables = list(self.config.tables.keys())
        for table_name in tables:
            name = self.config.get_parameters_advice_name(JobKind.advice.value, table_name)
            created_job = self._create_job(parameters_name=name)
            self.jobs[JobKind.advice] = created_job
            self._download_specific_result(JobKind.advice, Results.ADVICE)

        for table_name, advise_parameters in self.results.advice.items():
            self.set_parameters(
                k=advise_parameters["k"],
                use_categorical_reduction=advise_parameters["use_categorical_reduction"],
                ncp=advise_parameters["ncp"],
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

    def _get_results_volume_name(self) -> str:
        if self.config.results_volume and self.config.results_volume.metadata.name:
            return self.config.results_volume.metadata.name
        return "user-volume-" + str(self.client.users.get_me().id)

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
        exclude_replacement_strategy: ExcludeVariablesMethod | None = None,
        imputation_method: ImputeMethod | None = None,
        imputation_k: int | None = None,
        imputation_training_fraction: float | None = None,
        dp_epsilon: float | None = None,
        dp_preprocess_budget_ratio: float | None = None,
        time_series_nf: int | None = None,
        time_series_projection_type: ProjectionType | None = None,
        time_series_nb_points: int | None = None,
        time_series_method: AlignmentMethod | None = None,
        known_variables: list[str] | None = None,
        target: str | None = None,
        closest_rate_percentage_threshold: float | None = None,
        closest_rate_ratio_threshold: float | None = None,
        categorical_hidden_rate_variables: list[str] | None = None,
    ):
        """
        Set the parameters for the table.

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
        exclude_replacement_strategy : ExcludeVariablesMethod, optional
            Strategy for replacing excluded variables. Options: ROW_ORDER, COORDINATE_SIMILARITY.
        imputation_method
            Method for imputing missing values.
            Options:
                ImputeMethod.KNN
                ImputeMethod.MODE
                ImputeMethod.MEDIAN
                ImputeMethod.MEAN
                ImputeMethod.FAST_KNN.
        imputation_k
            Number of neighbors to use for imputation if the method is KNN or FAST_KNN.
        imputation_training_fraction
            Fraction of the dataset to use for training the imputation model
            when using KNN or FAST_KNN.
        dp_epsilon
            Epsilon value for differential privacy.
        dp_preprocess_budget_ratio
            Budget ration to allocate when using differential privacy avatarization.
        time_series_nf
            In time series context, number of degrees of freedom to
            retain in time series projections.
        time_series_projection_type
            In time series context, type of projection for time series.
            Options: ProjectionType.FCPA, ProjectionType.FLATTEN default is FCPA.
        time_series_method
            In time series context, method for aligning series.
            Options: AlignmentMethod.SPECIFIED
                    AlignmentMethod.MAX
                    AlignmentMethod.MIN
                    AlignmentMethod.MEAN.
        time_series_nb_points
            In time series context, number of points to generate for time series.
        known_variables
            List of known variables to be used for privacy metrics.
            These are variables that could be easily known by an attacker.
        target
            Target variable to predict, used for signal metrics.
        """
        imputation = imputation_method.value if imputation_method else None
        replacement_strategy = (
            exclude_replacement_strategy.value if exclude_replacement_strategy else None
        )
        if k and dp_epsilon:
            raise ValueError(
                "Expected either k or dp_epsilon to be set, not both. "
                "If you want to use differential privacy, set dp_epsilon and remove k."
            )
        # reset the parameters if they were already set
        if self.config.avatarization and self.config.avatarization.get(table_name):
            del self.config.avatarization[table_name]
        if self.config.avatarization_dp and self.config.avatarization_dp.get(table_name):
            del self.config.avatarization_dp[table_name]
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
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_replacement_strategy=replacement_strategy,
            )

        elif dp_epsilon:
            # use dp in avatarization
            self.config.create_avatarization_dp_parameters(
                table_name=table_name,
                epsilon=dp_epsilon,
                ncp=ncp,
                preprocess_budget_ratio=dp_preprocess_budget_ratio,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_replacement_strategy=replacement_strategy,
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

        self.config.create_privacy_metrics_parameters(
            table_name=table_name,
            ncp=ncp,
            use_categorical_reduction=use_categorical_reduction,
            imputation_method=imputation,
            imputation_k=imputation_k,
            imputation_training_fraction=imputation_training_fraction,
            known_variables=known_variables,
            target=target,
            closest_rate_percentage_threshold=closest_rate_percentage_threshold,
            closest_rate_ratio_threshold=closest_rate_ratio_threshold,
            categorical_hidden_rate_variables=categorical_hidden_rate_variables,
        )

        self.config.create_signal_metrics_parameters(
            table_name=table_name,
            ncp=ncp,
            use_categorical_reduction=use_categorical_reduction,
            imputation_method=imputation,
            imputation_k=imputation_k,
            imputation_training_fraction=imputation_training_fraction,
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
                Union[AvatarizationParameters, AvatarizationDPParameters, PrivacyMetricsParameters]
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
            self.config.avatarization_dp is not None
            and table_name in self.config.avatarization_dp.keys()
        ):
            # DP avatarization parameters
            params = self.config.avatarization_dp[table_name]
            if isinstance(params, AvatarizationDPParameters):
                current_params.update(
                    {
                        "dp_epsilon": params.epsilon if params.epsilon else None,
                        "dp_preprocess_budget_ratio": params.preprocess_budget_ratio
                        if params.preprocess_budget_ratio
                        else None,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))

        elif (
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
                "closest_rate_percentage_threshold": pm_params.closest_rate_percentage_threshold,
                "closest_rate_ratio_threshold": pm_params.closest_rate_ratio_threshold,
                "categorical_hidden_rate_variables": pm_params.categorical_hidden_rate_variables,
            }
            current_params.update(to_update)

        return current_params

    def _extract_exclude_parameters(self, params) -> dict:
        """Extract exclude variables parameters from parameter object.

        Parameters
        ----------
        params:
            The parameters object that contains exclude_variables information.

        Returns
        -------
        A dictionary containing exclude_variable_names and exclude_replacement_strategy parameters.
        """
        result = {}
        if params.exclude_variables:
            result["exclude_variable_names"] = (
                params.exclude_variables["variable_names"]
                if params.exclude_variables["variable_names"]
                else None
            )
            result["exclude_replacement_strategy"] = (
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

    def run(self, jobs_to_run: list[JobKind] = JOB_EXECUTION_ORDER):
        yaml = self.get_yaml()

        self.client.resources.put_resources(
            set_name=self.set_name,
            yaml_string=yaml,
        )
        jobs_to_run = sorted(jobs_to_run, key=lambda job: JOB_EXECUTION_ORDER.index(job))
        for parameters_name in jobs_to_run:
            depends_on = []
            if (
                parameters_name == JobKind.signal_metrics
                or parameters_name == JobKind.privacy_metrics
            ):
                if JobKind.standard in self.jobs.keys():
                    depends_on = [self.jobs[JobKind.standard].Location]

            elif parameters_name == JobKind.report:
                if not self.jobs.get(JobKind.privacy_metrics) or not self.jobs.get(
                    JobKind.signal_metrics
                ):
                    raise ValueError(
                        "Expected Privacy and Signal to be created to run report got {jobs_to_run}"
                    )
                depends_on = [
                    self.jobs[JobKind.privacy_metrics].Location,
                    self.jobs[JobKind.signal_metrics].Location,
                ]

            created_job = self._create_job(
                parameters_name=parameters_name.value,
                depends_on=depends_on,
            )
            self.jobs[parameters_name] = created_job
        return self.jobs

    def _create_job(
        self,
        parameters_name: str,
        depends_on: list[str] = [],
    ):
        # FIXME: use the create_job method from the client instead of creating the request manually
        # the create_job method doesn't return the right object for now.
        print(f"Creating {parameters_name} job")  # noqa: T201
        request = JobCreateRequest(
            set_name=self.set_name, parameters_name=parameters_name, depends_on=depends_on
        )
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/jobs",  # noqa: F541
            "json_data": request,
        }
        created_job = JobCreateResponse(**self.client.send_request(**kwargs))
        return created_job

    def get_job(self, job_name: JobKind) -> JobResponse:
        """
        Get a job by name.

        Parameters
        ----------
        job_name
            The name of the job to get.

        Returns
        -------
        JobCreateResponse
            The job object.
        """
        if job_name not in self.jobs.keys():
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        return self.client.jobs.get_job_status(self.jobs[job_name].name)

    def get_status(self, job_name: JobKind):
        """
        Get the status of a job by name.
        Parameters
        ----------
        job_name
            The name of the job to get.
        """
        return self.get_job(job_name).status

    def _retrieve_job_result_urls(self, job_name: JobKind):
        """
        Get the result of a job by name.

        Parameters
        ----------
        job_name
            The name of the job to get.
        """
        job = self.get_job(job_name)
        if job.status in ERROR_STATUSES:
            if job.exception:
                raise ValueError(f"Job {job_name} failed with exception: {job.exception}")
            raise ValueError("internal error")

        while not job.done:
            time.sleep(DEFAULT_RETRY_INTERVAL)
            job = self.get_job(job_name)
            if job.status in ERROR_STATUSES:
                if job.exception:
                    raise ValueError(f"Job {job_name} failed with exception: {job.exception}")
                raise ValueError("internal error")
            if job.status == "finished":
                break

        self.results_urls[job_name] = self.client.results.get_results(self.jobs[job_name].name)

    def get_specific_result_urls(
        self,
        job_name: JobKind,
        result: Results = Results.SHUFFLED,
    ) -> list[str]:
        if job_name not in self.jobs.keys():
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        if job_name not in self.results_urls:
            self._retrieve_job_result_urls(job_name)
        return self.results_urls[job_name][result]

    def _download_all_files(self):
        for job_name in self.jobs.keys():
            if not self.results_urls or job_name not in self.results_urls.keys():
                self._retrieve_job_result_urls(job_name)
            for result in self.results_urls[job_name].keys():
                for table_name in self.config.tables.keys():
                    if result in Results:
                        if Results(result) in RESULTS_TO_STORE:
                            self.get_specific_result(table_name, job_name, Results(result))

    def _download_specific_result(
        self,
        job_name: JobKind,
        result_name: Results,
    ) -> None:
        urls = self.get_specific_result_urls(job_name=job_name, result=result_name)
        for url in urls:
            result = self.file_downloader.download_file(url)
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
        self, url: str, result_name: Results, job_name: JobKind
    ) -> dict[str, Any] | None:
        match result_name:
            case Results.FIGURES:
                return self._get_figure_metadata(url)
            case Results.METADATA:
                return {"kind": job_name}
            case _:
                return None

    def _get_figure_metadata(self, url: str) -> dict[str, Any] | None:
        figures_metadatas = self.file_downloader.download_file(
            self.results_urls[JobKind.standard][Results.FIGURES_METADATA][0]
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
        if table_name not in self.config.tables.keys():
            raise ValueError(f"Expected table '{table_name}' to be created.")
        if job_name not in self.jobs.keys():
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        if self.results.get_results(table_name, result, job_name) is None:
            self._download_specific_result(job_name, result)
        return self.results.get_results(table_name, result, job_name)

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

    def download_report(self, path: str | None = None):
        """
        Download the report.

        Parameters
        ----------
        path
            The path to save the report.
        """
        if self.results_urls.get(JobKind.report) is None:
            self._retrieve_job_result_urls(JobKind.report)
        report = self.results_urls[JobKind.report][Results.REPORT][0]
        self.file_downloader.download_file(report, path=path)

    def _get_user_results_volume(self) -> str:
        """
        Get the results volume.

        Returns
        -------
        dict
            The user volume.
        """
        return self.client.resources.get_user_volume(
            volume_name=self._get_results_volume_name(), set_name=self.set_name, purpose="results"
        )

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

        print(f"--- Avatarization parameters for {table_name}: ---")  # noqa: T201

        print(asdict(self.config.avatarization[table_name]))  # noqa: T201
        print("\n")  # noqa: T201
        print(f"--- Privacy metrics for {table_name}: ---")  # noqa: T201
        print(asdict(self.config.privacy_metrics[table_name]))  # noqa: T201
        print("\n")  # noqa: T201
        print(f"--- Signal metrics for {table_name}: ---")  # noqa: T201
        print(asdict(self.config.signal_metrics[table_name]))  # noqa: T201

    def _get_url_results_volume(self):
        return yaml.safe_load(self._get_user_results_volume())["spec"]["url"]

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

    def from_yaml(self, yaml_path: str) -> None:
        """Create a Runner object from a YAML configuration.

        Parameters
        ----------
        yaml
            The path to the yaml to transform.

        Returns
        -------
        Runner
            A Runner object configured based on the YAML content.
        """
        list_config = self._load_yaml_config(yaml_path)
        self._process_yaml_config(list_config)

    def _load_yaml_config(self, yaml_path: str) -> list[dict]:
        """Load the YAML configuration from a file."""
        with open(yaml_path, "r") as file:
            config = yaml.safe_load_all(file)
            return list(config)  # Convert generator to list

    def _ensure_results_volume(self):
        """Ensure the results volume is created."""
        if self.config.results_volume is None:
            self.config.create_results_volume(
                url=self._get_url_results_volume(),
                result_volume_name=self._get_results_volume_name(),
            )

    def _process_yaml_config(self, list_config: list[dict]) -> None:
        """Process the YAML configuration into parameters and links."""
        parameters: dict[str, dict] = {}
        links: dict[str, dict] = {}

        for item in list_config:
            kind = item.get("kind")
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})

            if kind == "AvatarVolume":
                self.config.create_volume(volume_name=metadata["name"], url=spec["url"])

            elif kind == "AvatarSchema":
                self._process_avatar_schema(spec, metadata, links)

            elif kind in {
                "AvatarParameters",
                "AvatarSignalMetricsParameters",
                "AvatarPrivacyMetricsParameters",
            }:
                self._process_parameters(spec, parameters)

        self._apply_links(links)

        self._apply_parameters(parameters)

    def _process_avatar_schema(self, spec: dict, metadata: dict, links: dict):
        """Process AvatarSchema kind from the YAML configuration."""
        if metadata["name"].endswith("_avatarized"):
            return
        for table in spec.get("tables", []):
            self._process_table(table, links)

    def _process_table(self, table: dict, links: dict):
        """Process a single table from the AvatarSchema."""
        self._ensure_results_volume()
        try:
            base = self.client.results.get_upload_url()
            user_specific_path = base + f"/{table['name']}"
            access_url = f"{self.client.base_url}/access?url=" + user_specific_path
            self.file_downloader.download_file(url=access_url)
            original_volume = table["data"]["volume"]
        except FileNotFoundError:
            print(f"Error downloading file {table['data']['file']}")  # noqa: T201
            print(  # noqa: T201
                f"File is not available in the server, upload it with runner.upload_file(table_name='{table['name']}', data='{table['data']['file']}')"  # noqa: E501
            )
            original_volume = VOLUME_NAME

        primary_key = None
        foreign_keys = []
        time_series_time = None
        types: dict[str, ColumnType] = {}
        if table.get("columns"):
            primary_key = next(
                (col["field"] for col in table["columns"] if col.get("primary_key")),
                None,
            )
            foreign_keys = [
                column["field"]
                for column in table["columns"]
                if column.get("identifier") and not column.get("primary_key")
            ]
            time_series_time = next(
                (col["field"] for col in table["columns"] if col.get("time_series_time")),
                None,
            )
            types = {
                col["field"]: ColumnType(col["type"]) for col in table["columns"] if col["type"]
            }

        self.config.create_table(
            table_name=table["name"],
            original_volume=original_volume,
            original_file=table["data"]["file"],
            avatar_volume=table["avatars_data"]["volume"] if "avatars_data" in table else None,
            avatar_file=table["avatars_data"]["volume"] if "avatars_data" in table else None,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            time_series_time=time_series_time,
            types=types,
            individual_level=table.get("individual_level"),
        )

        if table.get("links", []):
            for link in table["links"]:
                links[table["name"]] = link

    def _process_parameters(self, spec: dict, parameters: dict):
        """Process parameters from the YAML configuration."""
        for param_type in [
            "avatarization",
            "time_series",
            "privacy_metrics",
            "signal_metrics",
        ]:
            for table_name, params in spec.get(param_type, {}).items():
                parameters.setdefault(table_name, {}).update({param_type: params})

    def _apply_links(self, links: dict):
        """Apply links to the configuration."""
        for table_name, link in links.items():
            self.add_link(
                parent_table_name=table_name,
                parent_field=link["field"],
                child_table_name=link["to"]["table"],
                child_field=link["to"]["field"],
            )

    def _apply_parameters(self, parameters: dict):
        """Apply parameters to the configuration."""
        for table_name, params in parameters.items():
            avatarization = params.get("avatarization", {})
            time_series = params.get("time_series", {})
            privacy_metrics = params.get("privacy_metrics", {})

            exclude_replacement_strategy, exclude_variable_names = self._process_exclude_variables(
                avatarization
            )
            imputation_method, imputation_k, imputation_training_fraction = (
                self._process_imputation(avatarization)
            )
            time_series_projection_type, time_series_nf = self._process_time_series_projection(
                time_series
            )
            time_series_method, time_series_nb_points = self._process_time_series_alignment(
                time_series
            )

            self.set_parameters(
                table_name=table_name,
                k=avatarization.get("k"),
                ncp=avatarization.get("ncp"),
                use_categorical_reduction=avatarization.get("use_categorical_reduction"),
                column_weights=avatarization.get("column_weights"),
                exclude_variable_names=exclude_variable_names,
                exclude_replacement_strategy=exclude_replacement_strategy,
                imputation_method=imputation_method,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                time_series_nf=time_series_nf,
                time_series_projection_type=time_series_projection_type,
                time_series_nb_points=time_series_nb_points,
                time_series_method=time_series_method,
                known_variables=privacy_metrics.get("known_variables"),
                target=privacy_metrics.get("target"),
            )

    def _process_exclude_variables(self, avatarization: dict):
        """Process exclude variables from avatarization parameters."""
        exclude_replacement_strategy = None
        exclude_variable_names = None
        if exclude_vars := avatarization.get("exclude_variables", {}):
            exclude_replacement_strategy = self._get_enum_value(
                ExcludeVariablesMethod, exclude_vars.get("replacement_strategy")
            )
            exclude_variable_names = exclude_vars.get("variable_names")
        return exclude_replacement_strategy, exclude_variable_names

    def _process_imputation(self, avatarization: dict):
        """Process imputation parameters."""
        imputation_method = None
        imputation_k = None
        imputation_training_fraction = None
        if imputation := avatarization.get("imputation"):
            imputation_method = self._get_enum_value(ImputeMethod, imputation.get("method"))
            imputation_k = imputation.get("k")
            imputation_training_fraction = imputation.get("training_fraction")
        return imputation_method, imputation_k, imputation_training_fraction

    def _process_time_series_projection(self, time_series: dict):
        """Process time series projection parameters."""
        time_series_projection_type = None
        time_series_nf = None
        if projection := time_series.get("projection"):
            time_series_projection_type = self._get_enum_value(
                ProjectionType, projection.get("type")
            )
            time_series_nf = projection.get("nf")
        return time_series_projection_type, time_series_nf

    def _process_time_series_alignment(self, time_series: dict):
        """Process time series alignment parameters."""
        time_series_method = None
        time_series_nb_points = None
        if alignment := time_series.get("alignment"):
            time_series_method = self._get_enum_value(AlignmentMethod, alignment.get("method"))
            time_series_nb_points = alignment.get("nb_points")
        return time_series_method, time_series_nb_points

    def _get_enum_value(self, enum_class, value: str | None):
        if value is None:
            return None
        try:
            return enum_class(value)
        except ValueError:
            return None

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
