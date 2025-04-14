import io
import json
import secrets
import string
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from avatar_yaml import Config as Config
from avatar_yaml.models.parameters import (
    AlignmentMethod,
    ExcludeVariablesMethod,
    ImputeMethod,
    ProjectionType,
)
from avatar_yaml.models.schema import ColumnType, LinkMethod

from avatars.client import ApiClient
from avatars.models import JobCreateRequest, JobCreateResponse, JobKind, JobResponse

VOLUME_NAME = "input"

JOB_EXECUTION_ORDER = [
    JobKind.standard,
    JobKind.signal_metrics,
    JobKind.privacy_metrics,
    JobKind.report,
]

ERROR_STATUSES = ["parent_error", "error"]

READY_STATUSES = ["finished", *ERROR_STATUSES]

DEFAULT_RETRY_INTERVAL = 5


class Results(StrEnum):
    SHUFFLED = "shuffled"
    UNSHUFFLED = "unshuffled"
    PRIVACY_METRICS = "privacy_metrics"
    SIGNAL_METRICS = "signal_metrics"
    REPORT_IMAGES = "report_images"
    PROJECTIONS_ORIGINAL = "projections-original"
    PROJECTIONS_AVATARS = "projections-avatars"
    METADATA = "run_metadata"
    REPORT = "report"


TypeResults = dict | pd.DataFrame | str | list[dict]

mapping_result_to_file_name = {
    Results.SHUFFLED: "shuffled",
    Results.UNSHUFFLED: "unshuffled",
    Results.PRIVACY_METRICS: "privacy.json",
    Results.SIGNAL_METRICS: "signal.json",
    Results.PROJECTIONS_ORIGINAL: "projections.original",
    Results.PROJECTIONS_AVATARS: "projections.avatars",
    Results.METADATA: "run_metadata.json",
    Results.REPORT: "report.md",
}


class Runner:
    def __init__(self, api_client: ApiClient, seed: int | None = None) -> None:
        self.set_name = "".join(secrets.choice(string.ascii_letters) for _ in range(12))
        self.config = Config(set_name=self.set_name, seed=seed)
        self.client = api_client
        self.jobs: dict[JobKind | str, JobCreateResponse] = {}
        self.results_urls: dict[JobKind, dict[str, list[str]]] = {}
        self.results: dict[JobKind, dict[str, list[TypeResults]]] = {}

    def add_table(
        self,
        table_name: str,
        data: str | pd.DataFrame,
        primary_key: str | None = None,
        foreign_keys: list | None = None,
        time_series_time: str | None = None,
        types: dict[str, ColumnType] | None = None,
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
        extension = ".csv" if isinstance(data, pd.DataFrame) else Path(data).suffix
        file = table_name + extension
        self.client.upload_file(data=data, key=file)
        avatar_file = None
        if avatar_data is not None:
            avatar_file = table_name + "_avatars" + extension
            self.client.upload_file(data=avatar_data, key=avatar_file)

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

    def _get_results_volume_name(self) -> str:
        return "user-volume-" + str(self.client.users.get_me().id)

    def add_link(
        self,
        parent_table_name: str,
        parent_field: str,
        child_table_name: str,
        child_field: str,
        method: LinkMethod = LinkMethod.LINEAR_SUM_ASSIGNMENT,  # type: ignore[assignment]
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
            parent_table_name, child_table_name, parent_field, child_field, method
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
        """Set the parameters for the table."""
        imputation = imputation_method.value if imputation_method else None
        if k:
            replacement_strategy = (
                exclude_replacement_strategy.value if exclude_replacement_strategy else None
            )
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
                if len(self.config.tables) > 1:
                    continue

            created_job = self._create_job(
                parameters_name=parameters_name.value,
                depends_on=depends_on,
            )
            self.jobs[parameters_name] = created_job
        return self.jobs

    def run_from_yaml(
        self,
        yaml: Path,
        parameters_name: str,
        depends_on: list[str] | None = None,
    ):
        """Run a job from a yaml config.
        Parameters
        ----------
        yaml
            The path to the yaml config.
        parameters_name
            The name of the jobs to run
        depends_on
            The dependencies of the job to run.
        """
        str_yaml = yaml.read_text()
        self.client.resources.put_resources(
            set_name=self.set_name,
            yaml_string=str_yaml,
        )

        created_job = self._create_job(
            parameters_name=parameters_name,
            depends_on=depends_on,
        )

        self.jobs[parameters_name] = created_job
        return created_job

    def _create_job(
        self,
        parameters_name: str,
        depends_on: list[str] | None = None,
    ):
        # FIXME: use the create_job method from the client instead of creating the request manually
        # the create_job method doesn't return the right object for now.
        print(f"Creating {parameters_name} job")
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

    def _get_all_urls_results(self):
        """
        Get all url results.
        """
        for job_name in self.jobs.keys():
            self._retrieve_job_result_urls(job_name)
        return self.results_urls

    def _download_file_using_url(self, url, path: str | None = None) -> TypeResults:
        fileaccess = self.client.results.get_permission_to_download(url)
        data_str = self.client.download_file(fileaccess, path=path)
        if url.endswith(".json"):
            if not data_str.strip().startswith("["):
                # Ensures the content is wrapped in a list,
                # to handle cases where the JSON is not in an array format.
                data_str = f"[{data_str}]"
            data = json.loads(data_str)
        elif url.endswith(".csv"):
            data = pd.read_csv(io.StringIO(data_str))
        elif url.endswith(".pdf") or url.endswith(".md"):
            data = f"File downloaded successfully to {path}"
        return data

    def _download_all_files(self):
        self._get_all_urls_results()
        for job_name, results in self.results_urls.items():
            job = self.results.setdefault(job_name, {})
            for results_name, urls in results.items():
                if (
                    results_name == Results.REPORT_IMAGES.value
                    or results_name == Results.REPORT.value
                ):
                    continue

                for url in urls:
                    data = self._download_file_using_url(url)
                    result_filename = mapping_result_to_file_name[results_name]

                    if results_name in {
                        Results.PRIVACY_METRICS.value,
                        Results.SIGNAL_METRICS.value,
                    }:
                        table_name = data[0]["metadata"]["table_name"]
                        table = job.setdefault(table_name, {})
                        table.setdefault(Results(results_name), []).append(data[0])
                    else:
                        table_name = Path(url).stem.split(f".{result_filename}")[0]
                        table = job.setdefault(table_name, {})
                        table[Results(results_name)] = data

    def get_specific_result(
        self,
        table_name: str,
        job_name: JobKind,
        result: Results = Results.SHUFFLED,
    ) -> TypeResults:
        """
        Download a file from the results.
        Parameters
        ----------
        table_name
            The name of the table to search for.
        job_name
            The name of the job to search for.
        result
            The result to search for.
        Returns
        -------
        TypeResults
            Either a pandas DataFrame or a dictionary or a list of dictionnary depending on the result type.
        """
        if job_name not in self.jobs.keys():
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        if job_name not in self.results:
            self.get_all_results()
        return self.results[job_name][table_name][result]  # type: ignore[call-overload]

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
        if len(self.config.tables) > 1:
            raise NotImplementedError(
                "Report generation for multiple tables is not yet implemented."
            )
        if self.results_urls.get(JobKind.report) is None:
            self._retrieve_job_result_urls(JobKind.report)
        report = self.results_urls[JobKind.report][Results.REPORT][0]
        self._download_file_using_url(report, path=path)

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

    def _get_url_results_volume(self):
        return yaml.safe_load(self._get_user_results_volume())["spec"]["url"]

    def kill(self):
        pass

    def shuffled(self, table_name: str) -> TypeResults:
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
        return self.get_specific_result(table_name, JobKind.standard, Results.SHUFFLED)

    def sensitive_unshuffled(self, table_name: str) -> TypeResults:
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
        return self.get_specific_result(table_name, JobKind.standard, Results.UNSHUFFLED)

    def privacy_metrics(self, table_name: str) -> TypeResults:
        """
        Get the privacy metrics.

        Parameters
        ----------
        table_name
            The name of the table to get the privacy metrics from.
        Returns
        -------
        dict
            The privacy metrics as a dictionary.
        """
        results = self.get_specific_result(
            table_name, JobKind.privacy_metrics, Results.PRIVACY_METRICS
        )
        if len(results) == 1:
            return results[0]  # type: ignore[return-value]
        return results

    def signal_metrics(self, table_name: str) -> TypeResults:
        """
        Get the signal metrics.

        Parameters
        ----------
        table_name
            The name of the table to get the signal metrics from.
        Returns
        -------
        dict
            The signal metrics as a dictionary.
        """
        results = self.get_specific_result(
            table_name, JobKind.signal_metrics, Results.SIGNAL_METRICS
        )
        if len(results) == 1:
            return results[0]  # type: ignore[return-value]
        return results

    def projections(
        self, table_name: str, job_name: JobKind = JobKind.standard
    ) -> tuple[TypeResults, TypeResults]:
        """
        Get the projections.

        Parameters
        ----------
        table_name
            The name of the table to get the projections from.
        job_name
            The name of the job to get the projections from by default from avatarization job.
        Returns
        -------
        pd.DataFrame
            The projections as a pandas DataFrame.
        """
        original_coordinates = self.get_specific_result(
            table_name, job_name, Results.PROJECTIONS_ORIGINAL
        )
        avatars_coordinates = self.get_specific_result(
            table_name, job_name, Results.PROJECTIONS_AVATARS
        )
        return original_coordinates, avatars_coordinates
