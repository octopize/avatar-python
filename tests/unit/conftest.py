from typing import Callable, Optional
from uuid import UUID, uuid4

import httpx
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from avatars.client import ApiClient
from avatars.models import FileAccess, FileCredentials, JobKind, JobResponse

RequestHandle = Callable[[httpx.Request], httpx.Response]


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
        base_url="http://localhost:8000",
        http_client=http_client,
        verify_auth=False,
    )


EXPECTED_KWARGS = ["get_jobs_returned_value"]


class FakeJobs:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}
        self.get_jobs_returned_value = kwargs.get("get_jobs_returned_value", None)

    def get_jobs(self):
        return self.get_jobs_returned_value

    def get_job_status(self, name):
        return JobResponseFactory().build(
            name="name",
            set_name="set_name",
            parameters_name="parameters_name",
            created_at="2023-10-01T00:00:00Z",
            kind=JobKind.standard,
            status="finished",
            exception="",
            done=True,
            progress=1.0,
        )


class FakeResults:
    table_name = f"table_{uuid4().hex[:8]}"

    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def get_permission_to_download(self, url):
        return FileAccess(
            url=url,
            credentials=FileCredentials(
                access_key_id="access_key_id", secret_access_key="secret_access_key"
            ),
        )

    def get_results(self, name):
        return {
            "shuffled": [f"fakeurl/{self.table_name}.shuffled-0.csv"],
            "unshuffled": [f"fakeurl/{self.table_name}.unshuffled-0.csv"],
            "privacy_metrics": [f"fakeurl/{self.table_name}.privacy.json"],
            "signal_metrics": [f"fakeurl/{self.table_name}.signal.json"],
            "report": [f"fakeurl/{self.table_name}.report.md"],
        }

    def get_upload_url(self):
        raise FileNotFoundError()


class FakeResources:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def put_resources(self, set_name, yaml_string):
        pass

    def get_user_volume(
        self,
        volume_name: str,
        set_name: str,
        purpose: str,
    ):
        yaml_volume = f"""kind: AvatarVolume
metadata:
  name: {volume_name}
spec:
  url: url
        """
        return yaml_volume


class FakeUser(BaseModel):
    id: UUID


class FakeUsers:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def get_me(self):
        return FakeUser(id=uuid4())


class FakeApiClient(ApiClient):
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}
        for key in kwargs:
            if key not in EXPECTED_KWARGS:
                raise ValueError(f"Unexpected keyword argument {key}")

        self.jobs = FakeJobs(*args, **kwargs)
        self.results = FakeResults(*args, **kwargs)
        self.resources = FakeResources(*args, **kwargs)
        self.users = FakeUsers(*args, **kwargs)
        self.base_url = "http://localhost:8000"

    def upload_file(self, data, key):
        return "File uploaded successfully"

    def download_file(self, fileaccess, path, table_name=None):
        if fileaccess.url.endswith(".csv"):
            return " 1, 2, 3\n4, 5, 6\n7, 8, 9"
        elif fileaccess.url.endswith(".json"):
            return '{"key": "value","metadata": {"table_name": "{table}"} }'.replace(
                "{table}", self.results.table_name
            )

    def send_request(self, method, url, **kwargs):
        return {"name": "test", "Location": ""}


class JobResponseFactory(ModelFactory[JobResponse]):
    __model__ = JobResponse
