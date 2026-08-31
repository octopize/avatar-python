import re
import warnings
from typing import Literal
from uuid import UUID

import httpx
from avatar_yaml import Config as YAMLConfig
from avatar_yaml.models.avatar_metadata import (
    DataRecipient,
    DataSubject,
    DataType,
    SensitivityLevel,
)
from avatar_yaml.models.parameters import ReportLanguage

from avatars import __version__
from avatars.base_client import ApiConnectionError
from avatars.client import ApiClient
from avatars.client_config import ClientConfig
from avatars.config import Config, config, get_config
from avatars.models import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    CompatibilityStatus,
    JobKind,
    JobResponse,
)
from avatars.runner import Runner


def _increment_display_name_version(name: str) -> str:
    """Append or increment a -vN suffix on a display name.

    Examples
    --------
    >>> _increment_display_name_version("my_dataset")
    'my_dataset-v1'
    >>> _increment_display_name_version("my_dataset-v1")
    'my_dataset-v2'
    >>> _increment_display_name_version("my_dataset-v9")
    'my_dataset-v10'

    """
    match = re.search(r"-v(\d+)$", name)
    if match:
        version = int(match.group(1)) + 1
        return name[: match.start()] + f"-v{version}"
    return name + "-v1"


class Manager:
    """High-level convenience facade for interacting with the Avatar API.

    The ``Manager`` wraps an authenticated :class:`avatars.client.ApiClient` instance
    and exposes a small, task‑oriented surface area so end users can:

    * authenticate using an API key
    * spin up a :class:`avatars.runner.Runner` (``create_runner`` / ``create_runner_from_yaml``)
    * quickly inspect recent jobs & results (``get_last_jobs`` / ``get_last_results``)
    * perform simple platform health checks (``get_health``)

    It deliberately hides the lower-level resource clients (``jobs``, ``results``, ``datasets`` …)
    unless you access the underlying ``auth_client`` directly. This keeps common workflows
    succinct while preserving an escape hatch for advanced usage. The ``Runner`` objects created
    through the manager inherit the authenticated context, so you rarely have to pass tokens or
    low-level clients around manually.

    Attributes
    ----------
    auth_client:
        The underlying :class:`avatars.client.ApiClient` used to perform all HTTP requests.

    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_client: ApiClient | None = None,
        api_key: str | None = None,
        config: ClientConfig | None = None,
        should_verify_compatibility: bool | None = None,
    ) -> None:
        """Initialize the manager with a base url or config.

        For on-premise deployment without dedicated SSL certificates, you can disable SSL
        verification:
        `manager = Manager(api_client=ApiClient(base_url=url, should_verify_ssl=False))`

        For API key authentication:
        `manager = Manager(base_url=url, api_key="your-api-key")`

        Using a ClientConfig object:
        ```
        manager = Manager(
            config=ClientConfig(base_api_url="https://...", api_key="your-api-key")
        )
        ```

        Args:
        ----
            base_url: The url of your actual server endpoint,
                e.g. base_url="https://avatar.company.co".
                Backwards compatible with older placeholder for the api endpoint (``/api`` suffix).
                If not provided, defaults to "https://octopize.app".

            api_client: Optional pre-configured ApiClient instance.
                Mutually exclusive with config, base_url, api_key.
            api_key: API key for authentication using api-key-v1 scheme.
                Can also be set via AVATAR_API_KEY environment variable.
                Mutually exclusive with config, api_client.
            config: Optional ClientConfig object containing all configuration settings.
                Must include an api_key.
                Mutually exclusive with base_url, api_key, api_client.
            should_verify_compatibility: Whether to verify client-server compatibility.
                If None, defaults to config.VERIFY_COMPATIBILITY.

        """
        # Mutual exclusivity checks - api_client is mutually exclusive with everything else
        if api_client is not None:
            conflicting_params = []
            if base_url is not None:
                conflicting_params.append("base_url")
            if api_key is not None:
                conflicting_params.append("api_key")
            if config is not None:
                conflicting_params.append("config")

            if conflicting_params:
                params_str = ", ".join(conflicting_params)
                raise ValueError(
                    f"Cannot provide both 'api_client' and other parameters ({params_str}). "
                    "Either pass a pre-configured ApiClient or configuration parameters, not both."
                )
            self.auth_client = api_client
        # ClientConfig is mutually exclusive with base_url and api_key
        elif config is not None:
            conflicting_params = []
            if base_url is not None:
                conflicting_params.append("base_url")
            if api_key is not None:
                conflicting_params.append("api_key")

            if conflicting_params:
                params_str = ", ".join(conflicting_params)
                raise ValueError(
                    f"Cannot provide both 'config' and other parameters ({params_str}). "
                    "Either pass a ClientConfig object or individual parameters, not both."
                )

            # Use the provided ClientConfig directly
            self.auth_client = ApiClient(config=config)
        else:
            # Create ClientConfig from individual parameters with defaults
            env_config = get_config()
            # If base_url is provided, override the env_config
            if base_url:
                # Derive BASE_API_URL from BASE_URL
                # This allows for backward compatibility with older placeholder for
                # BASE_URL environment variable. This now also sets
                # STORAGE_ENDPOINT_URL accordingly.
                final_base_url = base_url
                if base_url.endswith("/api"):
                    # Deprecated usage of base_url, but still support base_url with /api suffix
                    final_base_url = base_url.removesuffix("/api")
                env_config = Config(BASE_URL=final_base_url)

            if api_key is not None:
                # Override the API_KEY set from environment
                env_config.API_KEY = api_key

            client_config = ClientConfig.from_config(env_config)

            self.auth_client = ApiClient(config=client_config)

        if not self.auth_client.is_using_api_key():
            raise ValueError(
                "An API key is required. Pass api_key='...' or set the "
                "AVATAR_API_KEY environment variable."
            )

        # Perform compatibility check and connection verification for API key authentication
        self._verify_compatibility_if_needed(should_verify_compatibility)
        self._verify_connection()

    def _verify_compatibility_if_needed(self, should_verify: bool | None = None) -> None:
        """Verify client-server compatibility if needed.

        Args:
        ----
            should_verify: Whether to verify compatibility.
                If None, defaults to config.VERIFY_COMPATIBILITY.

        """
        if should_verify is None:
            should_verify = config.VERIFY_COMPATIBILITY

        if not should_verify:
            return

        response = self.auth_client.compatibility.is_client_compatible()

        incompatible_statuses = [
            CompatibilityStatus.incompatible,
            CompatibilityStatus.unknown,
        ]
        if response.status in incompatible_statuses:
            compat_error_message = "Client is not compatible with the server.\n"
            compat_error_message += f"Server message: {response.message}.\n"
            compat_error_message += f"Client version: {__version__}.\n"

            compat_error_message += "Most recent compatible client version: "
            compat_error_message += f"{response.most_recent_compatible_client}.\n"

            compat_error_message += "To update your client, you can run "
            compat_error_message += "`pip install --upgrade octopize.avatar`.\n"

            compat_error_message += "To ignore, you can set "
            compat_error_message += "should_verify_compatibility=False in Manager()."
            warnings.warn(compat_error_message, DeprecationWarning, stacklevel=2)
            raise DeprecationWarning(compat_error_message)

    def _verify_connection(self) -> None:
        """Verify that the API key is valid by calling an authenticated endpoint.

        Raises
        ------
        ApiConnectionError
            If the API is unreachable or the API key is invalid.

        """
        try:
            self.auth_client.users.get_me()
        except httpx.ConnectError as e:
            raise ApiConnectionError(
                "Failed to connect to the Avatar API. "
                "Please verify your base URL is correct and the server is reachable."
            ) from e
        except Exception as e:
            error_msg = str(e)
            if "authenticated" in error_msg.lower() or "401" in error_msg:
                raise ApiConnectionError(
                    "Failed to authenticate with the Avatar API. "
                    "Please verify your API key is correct."
                ) from e
            raise ApiConnectionError(f"Failed to connect to the Avatar API: {error_msg}") from e

    def create_runner(
        self,
        set_name: str,
        *,
        seed: int | None = None,
        max_distribution_plots: int | None = None,
        output_format: Literal["csv", "parquet"] | None = None,
        pia_data_recipient: DataRecipient = DataRecipient.UNKNOWN,
        pia_data_type: DataType = DataType.UNKNOWN,
        pia_data_subject: DataSubject = DataSubject.UNKNOWN,
        pia_sensitivity_level: SensitivityLevel = SensitivityLevel.UNDEFINED,
        report_language: ReportLanguage = ReportLanguage.EN,
    ) -> Runner:
        """Create a new runner."""
        return Runner(
            api_client=self.auth_client,
            display_name=set_name,
            seed=seed,
            max_distribution_plots=max_distribution_plots,
            output_format=output_format,
            pia_data_recipient=pia_data_recipient,
            pia_data_type=pia_data_type,
            pia_data_subject=pia_data_subject,
            pia_sensitivity_level=pia_sensitivity_level,
            report_language=report_language,
        )

    def create_runner_from_id(
        self,
        set_name: str | UUID,
    ) -> Runner:
        """Reconstruct a Runner from an existing set_name UUID with historical results.

        This method fetches the configuration and job history from a previous
        avatarization, allowing you to access results without re-running jobs.

        **Note**: If you call ``run()`` on the reconstructed runner, it will create
        a NEW set_name. A ``UserWarning`` is emitted with the old ``set_name`` so you
        can recover previous results if needed.

        Parameters
        ----------
        set_name : str | UUID
            The UUID of the resource set to load. This is the value of ``runner.set_name``
            after a job has been run.

        Returns
        -------
        Runner
            A reconstructed Runner with access to historical results.

        Raises
        ------
        TypeError
            If set_name is not a str or UUID.
        ValueError
            If the set_name string is not a valid UUID format.
        Exception
            If resources cannot be fetched from the API.

        See Also
        --------
        create_runner_from_name : Simpler method using a runner name

        Examples
        --------
        >>> set_name = runner.set_name  # Save this UUID after running
        >>> runner2 = manager.create_runner_from_id(set_name)
        >>> results = runner2.shuffled("customers") # Access old results without re-running jobs
        >>>
        >>> # Re-run
        >>> runner2.run(ignore_warnings=True) # will create new results with a new id,
        >>> # you can still access old results with the old id

        """
        if not isinstance(set_name, (str, UUID)):
            raise TypeError(f"set_name must be a str or UUID, got {type(set_name).__name__}")

        if isinstance(set_name, str):
            try:
                UUID(set_name)
            except (ValueError, AttributeError):
                raise ValueError(
                    f"Invalid set_name format: '{set_name}'. "
                    "Expected a valid UUID string (e.g., 'a1b2c3d4-e5f6-7890-abcd-ef1234567890')"
                ) from None

        set_name_str = str(set_name) if isinstance(set_name, UUID) else set_name

        yaml_string = self.auth_client.resources.get_resources(set_name_str)
        config = YAMLConfig.from_yaml(yaml_string)
        runner = self.create_runner(set_name=_increment_display_name_version(config.set_name))
        runner.config = config
        runner.set_name = set_name_str
        runner.jobs.set_name = set_name_str
        runner.jobs.config = config
        runner._populate_results_from_existing_jobs()  # noqa: SLF001
        return runner

    def get_last_results(self, count: int = 1) -> list[dict[str, str]]:
        """Get the last n results."""
        last_jobs = self.auth_client.jobs.get_jobs(limit=count).jobs

        results = []
        for job in last_jobs:
            result = self.auth_client.results.get_results(job.name)
            results.append(result)

        return results

    def get_last_jobs(self, count: int = 1, name: str | None = None) -> dict[str, JobResponse]:
        """Get the last n jobs, optionally filtered by name.

        Parameters
        ----------
        count
            Number of most recent jobs to return.
        name
            If provided, only return jobs whose name matches exactly.

        """
        jobs = self.auth_client.jobs.get_jobs(limit=count, display_name=name).jobs
        return {job.name: job for job in jobs}

    def get_health(self) -> dict[str, str]:
        """Get the health of the server."""
        health: dict[str, str] = self.auth_client.health.get_health()
        return health

    def get_jobs_by_name(self, name: str) -> list[JobResponse]:
        """Return all jobs whose name matches exactly.

        Parameters
        ----------
        name
            The human-readable run name (e.g. ``"my_dataset"``).

        """
        return self.auth_client.jobs.get_jobs(display_name=name).jobs

    def get_jobs_by_id(self, id: UUID | str) -> list[JobResponse]:
        """Return all jobs belonging to the given run ID.

        Parameters
        ----------
        id
            The UUID of the run (as a ``UUID`` or its string representation).

        """
        return self.auth_client.jobs.get_jobs(set_name=str(id)).jobs

    def get_last_set(self) -> list[JobResponse]:
        """Return all jobs belonging to the most recently created run (set_name)."""
        return self.auth_client.jobs.get_last_jobs().jobs

    def find_ids_by_name(self, set_name: str) -> list[tuple[str, list[JobResponse]]]:
        """Find all run UUIDs associated with a given set_name.

        Multiple runs can share the same set_name, each representing a different
        version. Jobs sharing the same UUID are grouped together.

        Parameters
        ----------
        set_name : str
            The human-readable name to search for (e.g., ``"my_dataset"``).
            This is the name passed to ``create_runner(set_name=...)``.

        Returns
        -------
        list[tuple[str, list[JobResponse]]]
            List of ``(uuid, jobs)`` tuples sorted by the most recent job creation
            time within each group (newest first). Each tuple contains:

            - ``uuid``: UUID string of the run
            - ``jobs``: All jobs belonging to that run

            Returns an empty list if no matching set_name is found.

        """
        all_non_advice_kinds: list[JobKind] = [k for k in JobKind if k != JobKind.advice]
        matching_jobs = self.auth_client.jobs.get_jobs(
            display_name=set_name, kind=all_non_advice_kinds
        ).jobs

        # Group jobs by set_name, preserving insertion order
        grouped: dict[str, list[JobResponse]] = {}
        for job in matching_jobs:
            key = str(job.set_name)
            grouped.setdefault(key, []).append(job)

        # Sort groups by the most recent job creation time (newest first)
        results = sorted(
            grouped.items(),
            key=lambda item: max(j.created_at for j in item[1]),
            reverse=True,
        )

        return results

    def create_runner_from_name(
        self,
        display_name: str,
    ) -> Runner:
        """Create a Runner from the most recent run associated with a display name.

        This is the primary method for reloading results from a previous run.
        It looks up all runs matching the given display name and returns a Runner
        loaded with the most recent one.

        If multiple runs share the same display name, the one with the most recent job
        creation time will be used. To load a specific run by UUID, use
        ``create_runner_from_id`` instead.

        Parameters
        ----------
        display_name : str
            The human-readable name given to the run (the ``set_name`` argument passed
            to ``create_runner``). Must match exactly (case-sensitive).

        Returns
        -------
        Runner
            A Runner instance loaded with results from the most recent matching run.

        Raises
        ------
        ValueError
            If no runs are found for the given display name.

        Examples
        --------
        >>> runner = manager.create_runner_from_name("my_dataset")
        >>> df = runner.shuffled("patients")
        >>> metrics = runner.privacy_metrics("patients")

        """
        results = self.find_ids_by_name(display_name)
        if not results:
            raise ValueError(f"No jobs found for display name '{display_name}'")

        most_recent_set_name = results[0][0]
        return self.create_runner_from_id(most_recent_set_name)

    def create_runner_from_yaml(self, yaml_path: str, set_name: str) -> Runner:
        """Create a new runner from a yaml file.

        Parameters
        ----------
            yaml_path: The path to the yaml file.
            set_name: Name of the set of resources.

        """
        runner = self.create_runner(set_name=_increment_display_name_version(set_name))
        runner.from_yaml(yaml_path)
        return runner

    def delete_job(self, name: str) -> BulkDeleteResponse:
        """Delete all jobs for a run identified by its name.

        Looks up all runs whose name matches exactly. If exactly one run
        is found, all its jobs are deleted. If multiple runs share the same
        name, a :exc:`ValueError` is raised with the commands to use
        :meth:`delete_job_by_id` for each run.

        Parameters
        ----------
        name
            The human-readable name given to the run (the ``set_name`` argument
            passed to ``create_runner``).

        Returns
        -------
        BulkDeleteResponse
            Response containing deleted and failed jobs.

        Raises
        ------
        ValueError
            If no run is found for the given name, or if multiple runs
            match and the caller must disambiguate by id.

        """
        matches = self.find_ids_by_name(name)
        if not matches:
            raise ValueError(f"No jobs found for display name '{name}'")
        if len(matches) > 1:
            commands = "\n".join(
                f'  manager.delete_job_by_id(UUID("{set_name}"))' for set_name, _ in matches
            )
            raise ValueError(
                f"Multiple runs found for display name '{name}'.\n"
                "Delete the desired run by set name:\n"
                f"{commands}"
            )
        _, jobs = matches[0]
        return self.delete_jobs([job.name for job in jobs])

    def delete_job_by_id(self, id: UUID | str) -> BulkDeleteResponse:
        """Delete all jobs belonging to a specific run identified by its id.

        Parameters
        ----------
        id
            The UUID (or its string representation) of the run whose jobs
            should be deleted.

        Returns
        -------
        BulkDeleteResponse
            Response containing deleted and failed jobs.

        """
        set_name_uuid = UUID(str(id))
        job_names = [
            job.name for job in self.auth_client.jobs.get_jobs(set_name=str(set_name_uuid)).jobs
        ]
        return self.delete_jobs(job_names)

    def delete_jobs(self, job_names: list[str]) -> BulkDeleteResponse:
        """Delete multiple jobs by name, batching in groups of up to 100.

        Parameters
        ----------
        job_names
            The names of the jobs to delete.

        Returns
        -------
        BulkDeleteResponse
            Aggregated response containing all deleted and failed jobs across batches.

        """
        all_deleted: list[JobResponse] = []
        all_failed: list[str] = []
        for i in range(0, len(job_names), 100):
            batch = job_names[i : i + 100]
            response = self.auth_client.jobs.bulk_delete_jobs(BulkDeleteRequest(job_names=batch))
            all_deleted.extend(response.deleted_jobs)
            all_failed.extend(response.failed_jobs)
        return BulkDeleteResponse(deleted_jobs=all_deleted, failed_jobs=all_failed)
