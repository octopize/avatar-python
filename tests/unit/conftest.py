import json
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID, uuid4

import httpx
import numpy as np
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
                "name": "",
                "parameters": {
                    "dataset_id": "faa1b3b9-ac2d-4e2c-bd6c-7df064c2d233",
                    "column_weights": None,
                    "ncp": 30,
                    "imputation": {"method": "fast_knn", "k": None, "training_fraction": 1.0},
                    "use_categorical_reduction": None,
                    "exclude_variables": None,
                    "k": 20,
                    "seed": None,
                },
            },
        }
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

    def get_results(self, job_name):
        results = {}
        if job_name == JobKind.privacy_metrics.value:
            results["privacy_metrics"] = [f"fakeurl/{self.table_name}.privacy.json"]
            results["meta_metrics"] = ["fakeurl/meta_metrics.privacy.json"]
            results["run_metadata"] = ["fakeurl/run_metadata.privacy-metrics.json"]
        elif job_name == JobKind.signal_metrics.value:
            results["signal_metrics"] = [f"fakeurl/{self.table_name}.signal.json"]
            results["meta_metrics"] = ["fakeurl/meta_metrics.signal.json"]
            results["run_metadata"] = ["fakeurl/run_metadata.signal-metrics.json"]
        elif job_name == JobKind.standard.value:
            results["shuffled"] = [f"fakeurl/{self.table_name}.shuffled-0.csv"]
            results["unshuffled"] = [f"fakeurl/{self.table_name}.unshuffled-0.csv"]
            results["original_projections"] = [
                f"fakeurl/{self.table_name}.projections.original-0.csv"
            ]
            results["avatar_projections"] = [
                f"fakeurl/{self.table_name}.projections.avatars-0.csv"
            ]
            results["figures"] = [f"fakeurl/{self.table_name}.2d_projection.html"]
            results["figures_metadata"] = ["fakeurl/figures_metadata.json"]
            results["run_metadata"] = ["fakeurl/run_metadata.avatarize.json"]
        elif job_name == JobKind.advice.value:
            results["advice"] = [f"{self.table_name}.advice.json"]
        elif job_name == JobKind.report.value:
            results["report"] = ["fakeurl/report.pdf"]
        return results

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

    def download_file(self, file_access, table_name=None):
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
        elif Path(file_access.url).name == "figures_metadata.json":
            return figures_metadata_factory(table_name or self.results.table_name)
        elif Path(file_access.url).name.endswith(".html"):
            return figures_factory()
        elif Path(file_access.url).name == "advice.json":
            return advice_factory(table_name or self.results.table_name)
        elif Path(file_access.url).name == "report.pdf":
            return b"report content"
        elif Path(file_access.url).name.endswith(".csv"):
            return string_table_factory()
        elif Path(file_access.url).name.endswith(".privacy.json"):
            return privacy_metrics_factory(self.results.table_name)
        elif Path(file_access.url).name.endswith(".signal.json"):
            return signal_metrics_factory(self.results.table_name)
        else:
            raise ValueError(f"Unexpected file access URL: {file_access.url}")

    def send_request(self, method, url, **kwargs):
        return {"name": kwargs["json_data"].parameters_name, "Location": ""}


class JobResponseFactory(ModelFactory[JobResponse]):
    __model__ = JobResponse
