"""Job launcher for orchestrating avatarization jobs with proper dependencies and validation."""

from typing import Any
from uuid import UUID

from avatar_yaml import Config
from avatar_yaml.models.advice import AdviceType

from avatars.client import ApiClient
from avatars.models import JobCreateRequest, JobCreateResponse, JobKind, JobResponse


class JobLauncher:
    """Orchestrates job creation with dependency management and prerequisite validation."""

    def __init__(self, client: ApiClient, config: Config) -> None:
        """Initialize the JobLauncher.

        Parameters
        ----------
        client
            The API client to interact with the backend.
        config
            The avatarization configuration.
        """
        self.client = client
        self.config = config
        self.set_name: str = ""
        self.jobs: dict[str, JobCreateResponse] = {}

    def launch_job(
        self,
        job_kind: JobKind,
        set_name: str,
    ) -> None:
        """Launch a job with automatic dependency resolution and validation.

        Parameters
        ----------
        job_kind
            The kind of job to launch.
        set_name
            The set name (UUID) for the job.
        Returns
        -------
        JobCreateResponse
            The created job response.

        Raises
        ------
        ValueError
            If required prerequisites are not met for the job.
        """
        self.set_name = set_name
        self._validate_job_prerequisites(job_kind)
        depends_on = self._get_job_dependencies(job_kind)
        self._create_jobs(job_kind=job_kind, depends_on=depends_on)

    def _create_jobs(self, job_kind: JobKind, depends_on) -> None:
        """Create all jobs based on the configuration and dependencies."""
        parameters_name = self.get_parameters_name(job_kind)
        created_job = self._create_job(parameters_name=parameters_name, depends_on=depends_on)
        self.jobs[parameters_name] = created_job

        # For report jobs, also create the PIA report
        if job_kind == JobKind.report:
            pia_parameters_name = self.get_parameters_name(job_kind, pia_report=True)
            pia_job = self._create_job(parameters_name=pia_parameters_name, depends_on=depends_on)
            self.jobs[pia_parameters_name] = pia_job

    def get_parameters_name(self, job_kind: JobKind, pia_report: bool = False) -> str:
        """Get the parameters name for a given job kind.

        Parameters
        ----------
        job_kind
            The kind of job to get parameters name for.

        Returns
        -------
        str
            The parameters name.
        """
        match job_kind:
            case JobKind.report:
                if pia_report:
                    return "report_pia"
                return "report"
            case JobKind.advice:
                return self.config.get_parameters_advice_name(
                    name="advice", advisor_type=[AdviceType.PARAMETERS]
                )
            case str():
                return job_kind
            case _:
                return job_kind.value

    def _validate_job_prerequisites(self, job_kind: JobKind) -> None:
        """Validate that prerequisites are met before launching a job.

        Parameters
        ----------
        job_kind
            The kind of job to validate.

        Raises
        ------
        ValueError
            If required prerequisites are not met.
        """
        match job_kind:
            case JobKind.standard:
                if not self.config.avatarization and not self.config.avatarization_dp:
                    raise ValueError(
                        "Expected k or epsilon to be set to run an avatarization job, "
                        "You have to set a k or epsilon parameter using `runner.set_parameter()`."
                    )

            case JobKind.signal_metrics | JobKind.privacy_metrics:
                # If standard job wasn't run, avatar tables must be provided
                if JobKind.standard.value not in self.jobs:
                    for avatar_table in self.config.avatar_tables.values():
                        if (
                            avatar_table.avatars_data is None
                            or avatar_table.avatars_data.file is None
                        ):
                            raise ValueError(
                                "Expected Avatar tables to be set to run signal/privacy metrics "
                                "job. You have to set avatar_data using `runner.add_table()`."
                            )

            case JobKind.report:
                if (
                    JobKind.privacy_metrics.value not in self.jobs
                    or JobKind.signal_metrics.value not in self.jobs
                ):
                    raise ValueError(
                        "Expected Privacy and Signal jobs to be created before running report."
                    )
            case _:
                pass

    def _get_job_dependencies(self, job_kind: JobKind) -> list[str]:
        """Get the list of job dependencies for a given job kind.

        Parameters
        ----------
        job_kind
            The kind of job to get dependencies for.

        Returns
        -------
        list[str]
            List of job locations that this job depends on.
        """
        match job_kind:
            case JobKind.signal_metrics | JobKind.privacy_metrics:
                avatarization_job_name = self.get_parameters_name(JobKind.standard)
                if avatarization_job_name in self.jobs:
                    return [self.jobs[avatarization_job_name].Location]

            case JobKind.report:
                privacy_metrics_job_name = self.get_parameters_name(JobKind.privacy_metrics)
                signal_metrics_job_name = self.get_parameters_name(JobKind.signal_metrics)
                return [
                    self.jobs[privacy_metrics_job_name].Location,
                    self.jobs[signal_metrics_job_name].Location,
                ]

            case _:
                pass
        return []

    def _create_job(
        self,
        parameters_name: str,
        depends_on: list[str] | None = None,
    ) -> JobCreateResponse:
        """Create a job via the API.

        Parameters
        ----------
        parameters_name
            The name of the parameters to use for the job.
        depends_on
            List of job locations this job depends on.

        Returns
        -------
        JobCreateResponse
            The created job response from the API.
        """
        if depends_on is None:
            depends_on = []

        request = JobCreateRequest(
            set_name=UUID(self.set_name), parameters_name=parameters_name, depends_on=depends_on
        )
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": "/jobs",
            "json_data": request,
        }
        created_job = JobCreateResponse(**self.client.send_request(**kwargs))
        return created_job

    def get_job_response(self, job_name: JobKind | str) -> JobCreateResponse:
        """Get a job by name.

        Parameters
        ----------
        job_name
            The name of the job to get (JobKind enum or string like "report_pia").

        Returns
        -------
        JobCreateResponse
            The job object.

        Raises
        ------
        ValueError
            If the job has not been created yet.
        """
        if isinstance(job_name, JobKind):
            job_name = self.get_parameters_name(job_name)
        if job_name not in self.jobs:
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        return self.jobs[job_name]

    def get_job_id(self, job_name: JobKind | str) -> str:
        """Get a job by name.

        Parameters
        ----------
        job_name
            The name of the job to get (JobKind enum or string like "report_pia").

        Returns
        -------
        str
            The job ID.

        Raises
        ------
        ValueError
            If the job has not been created yet.
        """
        job_create_response = self.get_job_response(job_name)
        return job_create_response.name

    def has_job(self, job_name: JobKind | str) -> bool:
        """Check if a job has been created.

        Parameters
        ----------
        job_name
            The name of the job to check.

        Returns
        -------
        bool
            True if the job exists, False otherwise.
        """
        if isinstance(job_name, JobKind):
            job_name = self.get_parameters_name(job_name)
        return job_name in self.jobs

    def get_launched_jobs(self) -> list[str]:
        """Get a list of all jobs that have been launched.

        Returns
        -------
        list[str]
            List of job kinds that have been launched.
        """
        return list(self.jobs.keys())

    def get_job_status(self, job_name: JobKind | str) -> JobResponse:
        """Get the full job status from the API.

        Parameters
        ----------
        job_name
            The name of the job to get status for (JobKind enum or string like "report_pia").

        Returns
        -------
        JobResponse
            The job status response from the API.

        Raises
        ------
        ValueError
            If the job has not been created yet.
        """
        job_id = self.get_job_id(job_name)
        return self.client.jobs.get_job_status(job_id)
