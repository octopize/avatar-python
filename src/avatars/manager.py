from uuid import UUID

from avatars.client import ApiClient
from avatars.models import JobResponse
from avatars.runner import Runner


class Manager:
    """High-level convenience facade for interacting with the Avatar API.

    The ``Manager`` wraps an authenticated :class:`avatars.client.ApiClient` instance
    and exposes a small, task‑oriented surface area so end users can:

    * authenticate once (``authenticate``)
    * spin up a :class:`avatars.runner.Runner` (``create_runner`` / ``create_runner_from_yaml``)
    * quickly inspect recent jobs & results (``get_last_jobs`` / ``get_last_results``)
    * perform simple platform health checks (``get_health``)
    * handle password reset flows (``forgotten_password`` / ``reset_password``)

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

    def __init__(self, base_url: str, api_client: ApiClient | None = None) -> None:
        """Initialize the manager with a base url.

        For on-premise deployment without dedicated SSL certificates, you can disable SSL
        verification:
        `manager = Manager(api_client=ApiClient(base_url=url, should_verify_ssl=False))`

        Args:
        -----
            base_url: The url of your actual server endpoint, e.g. base_url="https://avatar.company.co.
        """
        if api_client:
            self.auth_client = api_client
        else:
            self.auth_client = ApiClient(base_url=base_url)

    def authenticate(self, username: str, password: str) -> None:
        """Authenticate the user with the given username and password."""
        self.auth_client.authenticate(username, password)

    def forgotten_password(self, email: str) -> None:
        """Send a forgotten password email to the user."""
        self.auth_client.forgotten_password(email)

    def reset_password(
        self, email: str, new_password: str, new_password_repeated: str, token: str | UUID
    ) -> None:
        """Reset the password of the user."""
        if isinstance(token, str):
            token = UUID(token)
        self.auth_client.reset_password(email, new_password, new_password_repeated, token)

    def create_runner(self, set_name: str, seed: int | None = None) -> Runner:
        """Create a new runner."""
        return Runner(api_client=self.auth_client, display_name=set_name, seed=seed)

    def get_last_results(self, count: int = 1) -> list[dict[str, str]]:
        """Get the last n results."""
        all_jobs = self.auth_client.jobs.get_jobs().jobs

        last_jobs = all_jobs[-count:]
        results = []
        for job in last_jobs:
            result = self.auth_client.results.get_results(job.name)
            results.append(result)

        return results

    def get_last_jobs(self, count: int = 1) -> dict[str, JobResponse]:
        """Get the last n results."""
        all_jobs = self.auth_client.jobs.get_jobs().jobs

        last_jobs = all_jobs[-count:]
        results = {}
        for job in last_jobs:
            results[job.name] = job
        return results

    def get_health(self) -> dict[str, str]:
        """Get the health of the server."""
        return self.auth_client.health.get_health()

    def create_runner_from_yaml(self, yaml_path: str, set_name: str) -> Runner:
        """Create a new runner from a yaml file.
        Parameters
        ----------
            yaml_path: The path to the yaml file.
            set_name: Name of the set of resources.
        """
        runner = self.create_runner(set_name=set_name)
        runner.from_yaml(yaml_path)
        return runner
