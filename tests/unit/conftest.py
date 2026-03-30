import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import numpy as np
import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from avatars.client import ApiClient
from avatars.log import setup_logging
from avatars.models import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    CompatibilityResponse,
    CompatibilityStatus,
    FileAccess,
    FileCredentials,
    JobCreateRequest,
    JobCreateResponse,
    JobKind,
    JobResponse,
    JobResponseList,
    Login,
    LoginResponse,
    ResourceSetResponse,
)

RequestHandle = Callable[[httpx.Request], httpx.Response]

setup_logging()


def create_fake_job(
    name: str = "test_job",
    set_name: UUID | None = None,
    display_name: str = "test_dataset",
    kind: JobKind = JobKind.standard,
    status: str = "finished",
    parameters_name: str | None = None,
    created_at: datetime | None = None,
    done: bool = True,
    progress: float = 1.0,
    exception: str = "",
) -> JobResponse:
    """Create a fake JobResponse for testing.

    Parameters
    ----------
    name : str
        Job name (default: "test_job")
    set_name : UUID | None
        Set UUID (default: random UUID)
    display_name : str
        Display name for the dataset (default: "test_dataset")
    kind : JobKind
        Job type (default: JobKind.standard)
    status : str
        Job status (default: "finished")
    parameters_name : str | None
        Parameters name (default: matches job kind value)
    created_at : datetime | None
        Creation timestamp (default: now)
    done : bool
        Whether job is complete (default: True)
    progress : float
        Job progress 0-1 (default: 1.0)
    exception : str
        Exception message if any (default: "")

    Returns
    -------
    JobResponse
        A fully populated job object ready for testing

    Examples
    --------
    >>> # Simple usage - all defaults
    >>> job = create_fake_job()

    >>> # Custom set_name and display_name
    >>> job = create_fake_job(set_name=my_uuid, display_name="customers")

    >>> # Job from 5 days ago
    >>> job = create_fake_job(created_at=datetime.now(UTC) - timedelta(days=5))

    >>> # Privacy metrics job
    >>> job = create_fake_job(kind=JobKind.privacy_metrics, name="privacy_job")
    """
    if set_name is None:
        set_name = uuid4()
    if parameters_name is None:
        parameters_name = kind.value
    if created_at is None:
        created_at = datetime.now(UTC)

    return JobResponse(
        name=name,
        set_name=set_name,
        parameters_name=parameters_name,
        created_at=created_at,
        kind=kind,
        status=status,
        exception=exception,
        done=done,
        progress=progress,
        display_name=display_name,
    )


@pytest.fixture(autouse=True)
def no_sleep():
    """Patch time.sleep in avatars.runner to avoid real delays in unit tests."""
    with patch("avatars.runner.time.sleep"):
        yield


def mock_httpx_client(handler: Optional[RequestHandle] = None) -> httpx.Client:
    """Generate a HTTPX client with a MockTransport."""

    if handler is None:
        handler = lambda request: httpx.Response(200, json={})  # noqa: E731

    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="http://localhost:8000", transport=transport)  # nosec


def api_client_factory(handler: Optional[RequestHandle] = None) -> ApiClient:
    """Generate an API client with a mock transport.

    The handler returns an empty 200 response by default.
    Consider overriding it with a custom handler for more complex tests.
    """
    http_client = mock_httpx_client(handler)
    return ApiClient(
        base_url="http://localhost:8000/api",
        http_client=http_client,
        verify_auth=False,
    )


EXPECTED_KWARGS = ["jobs"]


class FakeJobs:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}
        self._get_jobs_returned_value: JobResponseList | None = kwargs.get(
            "get_jobs_returned_value", None
        )
        self._jobs: dict[str, JobResponse] = {}
        self.bulk_delete_calls: list[BulkDeleteRequest] = []

    def add_job(self, job: JobResponse) -> None:
        """Pre-populate a job into the fake store (for test setup)."""
        self._jobs[job.name] = job

    def create_job(self, request: JobCreateRequest) -> JobCreateResponse:
        name = str(uuid4())
        self._jobs[name] = JobResponse(
            name=name,
            set_name=request.set_name,
            parameters_name=request.parameters_name,
            display_name=request.parameters_name,
            created_at=datetime.now(timezone.utc),
            kind=JobKind.standard,
            status="pending",
            exception="",
            progress=50,
            done=False,
        )
        return JobCreateResponse(name=name, Location=f"/jobs/{name}")

    def get_jobs(self) -> JobResponseList:
        if self._get_jobs_returned_value is not None:
            return self._get_jobs_returned_value
        return JobResponseList(jobs=list(self._jobs.values()))

    def get_job_status(self, name: str) -> JobResponse:
        if name in self._jobs:
            return self._jobs[name]
        return JobResponseFactory().build(
            name=name,
            set_name=uuid4(),
            parameters_name=name,
            display_name=name,
            created_at="2023-10-01T00:00:00Z",
            kind=JobKind.standard,
            status="finished",
            done=True,
            progress=1.0,
        )

    def delete_job(self, job_name: str) -> JobResponse:
        if job_name not in self._jobs:
            raise ValueError(f"Job '{job_name}' not found")
        return self._jobs.pop(job_name)

    def bulk_delete_jobs(self, request: BulkDeleteRequest) -> BulkDeleteResponse:
        self.bulk_delete_calls.append(request)
        deleted: list[JobResponse] = []
        failed: list[str] = []
        for job_name in request.job_names:
            if job_name in self._jobs:
                deleted.append(self._jobs.pop(job_name))
            else:
                failed.append(job_name)
        return BulkDeleteResponse(deleted_jobs=deleted, failed_jobs=failed)


def privacy_metrics_factory(table_name: str) -> str:
    return json.dumps(
        {
            "local_cloaking": np.random.uniform(0, 100),
            "hidden_rate": np.random.uniform(0, 100),
            "metadata": {
                "table_name": table_name,
                "computation_type": "standalone",
                "reference": None,
            },
        }
    )


def signal_metrics_factory(table_name: str) -> str:
    return json.dumps(
        {
            "hellinger_mean": np.random.uniform(0, 100),
            "hellinger_std": np.random.uniform(0, 100),
            "metadata": {
                "table_name": table_name,
                "computation_type": "standalone",
                "reference": None,
            },
        }
    )


def run_metadata_factory() -> str:
    return """{
        'created_at': '2025-07-08T12:09:23.820284+00:00',
        'finished_at': '2025-07-08T12:09:24.362366+00:00'
        }"""


def figures_metadata_factory(table_name: str) -> str:
    return json.dumps(
        {
            "kind": "2d_projection",
            "filename": f"{table_name}.2d_projection.html",
            "table_name": table_name,
        }
    )


def figures_factory() -> str:
    return """<div>Test</div>"""


def meta_privacy_metrics_factory() -> str:
    return json.dumps({"meta_privacy": {np.random.uniform(1, 100)}})


def meta_signal_metrics_factory() -> str:
    return json.dumps({"meta_signal": {np.random.uniform(1, 100)}})


def string_table_factory() -> str:
    return """1, 2, 3
    4, 5, 6"""


def advice_factory(table_name: str) -> str:
    return json.dumps(
        {
            "table_name": table_name,
            "advice": {
                "ncp": 30,
                "imputation": {
                    "method": "fast_knn",
                    "k": 3,
                    "training_fraction": 1.0,
                    "return_data_imputed": False,
                },
                "use_categorical_reduction": None,
                "k": 20,
                "summary": "This is a fake advice",
            },
        },
    )


class FakeResults:
    def __init__(self, tables: list[str] | None = None):
        self.tables = tables or []

    def get_permission_to_download(self, url):
        return FileAccess(
            url=url,
            credentials=FileCredentials(
                access_key_id="access_key_id", secret_access_key="secret_access_key"
            ),
        )

    def get_permissions_to_download_batch(self, urls: list[str]):
        """Return FileAccess objects for all URLs in the batch."""
        return [
            FileAccess(
                url=url,
                credentials=FileCredentials(
                    access_key_id="access_key_id", secret_access_key="secret_access_key"
                ),
            )
            for url in urls
        ]

    def get_results(self, job_name):
        results = {}
        for table_name in self.tables:
            if job_name == JobKind.privacy_metrics.value:
                if "privacy_metrics" not in results:
                    results["privacy_metrics"] = []
                results["privacy_metrics"].append(f"fakeurl/{table_name}.privacy.json")
            elif job_name == JobKind.signal_metrics.value:
                if "signal_metrics" not in results:
                    results["signal_metrics"] = []
                results["signal_metrics"].append(f"fakeurl/{table_name}.signal.json")

            elif job_name == JobKind.standard.value:
                if "shuffled" not in results:
                    results["shuffled"] = []
                if "unshuffled" not in results:
                    results["unshuffled"] = []
                if "original_projections" not in results:
                    results["original_projections"] = []
                if "avatar_projections" not in results:
                    results["avatar_projections"] = []
                if "figures" not in results:
                    results["figures"] = []

                results["shuffled"].append(f"fakeurl/{table_name}.shuffled-0.csv")
                results["unshuffled"].append(f"fakeurl/{table_name}.unshuffled-0.csv")
                results["original_projections"].append(
                    f"fakeurl/{table_name}.projections.original-0.csv"
                )
                results["avatar_projections"].append(
                    f"fakeurl/{table_name}.projections.avatars-0.csv"
                )
                results["figures"].append(f"fakeurl/{table_name}.2d_projection.html")
            elif JobKind.advice.value in job_name:
                if "advice" not in results:
                    results["advice"] = []
                results["advice"].append(f"fakeurl/{table_name}.advice.json")

        if job_name == JobKind.privacy_metrics.value:
            results["meta_metrics"] = ["fakeurl/meta_metrics.privacy.json"]
            results["run_metadata"] = ["fakeurl/run_metadata.privacy-metrics.json"]
        elif job_name == JobKind.signal_metrics.value:
            results["meta_metrics"] = ["fakeurl/meta_metrics.signal.json"]
            results["run_metadata"] = ["fakeurl/run_metadata.signal-metrics.json"]
        elif job_name == JobKind.standard.value:
            results["figures_metadata"] = ["fakeurl/figures_metadata.json"]
            results["run_metadata"] = ["fakeurl/run_metadata.avatarize.json"]
        elif job_name == JobKind.report.value:
            results["report"] = ["report.pdf"]
        elif job_name == "report_pia":
            results["report"] = [f"{t}.report.pia.pdf" for t in self.tables]
        return results

    def get_upload_url(self):
        raise FileNotFoundError()


class FakeResources:
    def __init__(self):
        self._stored_resources: dict[str, str] = {}

    def put_resources(self, display_name, yaml_string):
        set_name = uuid4()
        self._stored_resources[str(set_name)] = yaml_string
        return ResourceSetResponse(set_name=set_name, display_name=display_name)

    def get_resources(self, set_name: str) -> str:
        """Return mock YAML for a resource set."""
        if set_name in self._stored_resources:
            return self._stored_resources[set_name]
        # Return a minimal valid YAML if not found
        return """---
kind: AvatarMetadata
metadata:
  name: avatar-metadata-test
spec:
  display_name: test_dataset
---
kind: AvatarSchema
metadata:
  name: schema
spec:
  tables:
    - name: table1
      data:
        volume: input
        file: table1.csv
"""


class FakeUser(BaseModel):
    id: UUID


class FakeUsers:
    def __init__(self):
        pass

    def get_me(self):
        return FakeUser(id=uuid4())


class FakeAuth:
    def __init__(self):
        pass

    def login(self, login: Login, timeout: Optional[int] = None):
        return


class FakeCompatibility:
    def __init__(self):
        pass

    def is_client_compatible(self):
        return CompatibilityResponse(
            message="Message from the server",
            status=CompatibilityStatus.incompatible,
            most_recent_compatible_client="1.0.0",
        )


class FakeApiClient(ApiClient):
    """Fake API client for unit testing.

    Provides mock implementations of all API endpoints without requiring
    a real server connection.

    Examples
    --------
    >>> # Simple usage with defaults
    >>> client = FakeApiClient()

    >>> # With pre-configured jobs
    >>> jobs = [create_fake_job(display_name="dataset1")]
    >>> for job in jobs:
    ...     client.jobs.add_job(job)

    >>> # With builder pattern via jobs attribute
    >>> client = FakeApiClient()
    >>> client.jobs.with_job(name="job1").with_job(name="job2")
    """

    jobs: FakeJobs  # type: ignore[assignment]

    def __init__(
        self,
        tables: list[str] | None = None,
    ):
        """Initialize FakeApiClient.

        Parameters
        ----------
        tables : list[str] | None
            List of table names to simulate in results.
        """
        self.tables = tables or []
        self.jobs = FakeJobs()  # type: ignore
        self.results = FakeResults(tables=self.tables)  # type: ignore
        self.resources = FakeResources()  # type: ignore
        self.users = FakeUsers()  # type: ignore
        self.base_url = "http://localhost:8000"
        self.auth = FakeAuth()  # type: ignore
        self.compatibility = FakeCompatibility()  # type: ignore
        self.timeout = 100
        # Initialize attributes needed for API key authentication
        self._api_key: Optional[str] = None
        self._headers: dict[str, str] = {}

    def set_header(self, key: str, value: str) -> None:
        """Set a header in the client."""
        self._headers[key] = value

    def _update_auth_tokens(
        self, resp: LoginResponse, *, headers: Optional[dict[str, str]] = None
    ):
        pass

    def upload_file(self, data, key):
        return "File uploaded successfully"

    def download_file(self, file_access):
        if Path(file_access.url).name == "meta_metrics.privacy.json":
            return meta_privacy_metrics_factory()
        elif Path(file_access.url).name == "meta_metrics.signal.json":
            return meta_signal_metrics_factory()
        elif Path(file_access.url).name == "run_metadata.privacy-metrics.json":
            return run_metadata_factory()
        elif Path(file_access.url).name == "run_metadata.signal-metrics.json":
            return run_metadata_factory()
        elif Path(file_access.url).name == "run_metadata.avatarize.json":
            return run_metadata_factory()

        table_name = Path(file_access.url).name.split(".")[0]
        if Path(file_access.url).name.endswith(".html"):
            return figures_factory()
        elif Path(file_access.url).name.endswith("advice.json"):
            return advice_factory(table_name)
        elif Path(file_access.url).name == "report.pdf":
            return b"report content"
        elif Path(file_access.url).name.endswith(".report.pia.pdf"):
            table_name = Path(file_access.url).name.split(".report.pia.")[0]
            return f"pia report content for {table_name}".encode()
        elif Path(file_access.url).name.endswith(".csv"):
            return string_table_factory()
        elif Path(file_access.url).name.endswith(".privacy.json"):
            return privacy_metrics_factory(table_name)
        elif Path(file_access.url).name.endswith(".signal.json"):
            return signal_metrics_factory(table_name)
        elif Path(file_access.url).name == "figures_metadata.json":
            return figures_metadata_factory(self.tables[0])

    def send_request(self, method, url, **kwargs):
        name = kwargs["json_data"].parameters_name
        self.jobs._jobs[name] = JobResponse(
            name=name,
            set_name=kwargs["json_data"].set_name,
            parameters_name=name,
            display_name=name,
            created_at=datetime.now(timezone.utc),
            kind=JobKind.standard,
            status="finished",
            exception="",
            progress=0,
            done=True,
        )
        return {"name": name, "Location": ""}


class JobResponseFactory(ModelFactory[JobResponse]):
    __model__ = JobResponse
    __check_model__ = False
