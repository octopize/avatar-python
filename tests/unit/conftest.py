import json
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID, uuid4

import httpx
import numpy as np
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from avatars.client import ApiClient
from avatars.models import (
    CompatibilityResponse,
    CompatibilityStatus,
    FileAccess,
    FileCredentials,
    JobKind,
    JobWithDisplayNameResponse,
    Login,
    LoginResponse,
    ResourceSetResponse,
)

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
            set_name=uuid4(),
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
    def __init__(self, tables: list[str] | None = None, *args, **kwargs):
        kwargs = kwargs or {}
        self.tables = tables or []

    def get_permission_to_download(self, url):
        return FileAccess(
            url=url,
            credentials=FileCredentials(
                access_key_id="access_key_id", secret_access_key="secret_access_key"
            ),
        )

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
            results["report"] = ["fakeurl/report.pdf"]
        return results

    def get_upload_url(self):
        raise FileNotFoundError()


class FakeResources:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def put_resources(self, display_name, yaml_string):
        return ResourceSetResponse(set_name=uuid4(), display_name=display_name)


class FakeUser(BaseModel):
    id: UUID


class FakeUsers:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def get_me(self):
        return FakeUser(id=uuid4())


class FakeAuth:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def login(self, login: Login, timeout: Optional[int] = None):
        return


class FakeCompatibility:
    def __init__(self, *args, **kwargs):
        kwargs = kwargs or {}

    def is_client_compatible(self):
        return CompatibilityResponse(
            message="Message from the server",
            status=CompatibilityStatus.incompatible,
            most_recent_compatible_client="1.0.0",
        )


class FakeApiClient(ApiClient):
    def __init__(self, tables: list[str] | None = None, *args, **kwargs):
        kwargs = kwargs or {}
        for key in kwargs:
            if key not in EXPECTED_KWARGS:
                raise ValueError(f"Unexpected keyword argument {key}")
        self.tables = tables or []
        self.jobs = FakeJobs(*args, **kwargs)  # type: ignore
        self.results = FakeResults(tables=self.tables)  # type: ignore
        self.resources = FakeResources(*args, **kwargs)  # type: ignore
        self.users = FakeUsers(*args, **kwargs)  # type: ignore
        self.base_url = "http://localhost:8000"
        self.auth = FakeAuth()  # type: ignore
        self.compatibility = FakeCompatibility()  # type: ignore
        self.timeout = 100

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
        elif Path(file_access.url).name.endswith(".csv"):
            return string_table_factory()
        elif Path(file_access.url).name.endswith(".privacy.json"):
            return privacy_metrics_factory(table_name)
        elif Path(file_access.url).name.endswith(".signal.json"):
            return signal_metrics_factory(table_name)
        elif Path(file_access.url).name == "figures_metadata.json":
            return figures_metadata_factory(self.tables[0])

    def send_request(self, method, url, **kwargs):
        return {"name": kwargs["json_data"].parameters_name, "Location": ""}


class JobResponseFactory(ModelFactory[JobWithDisplayNameResponse]):
    __model__ = JobWithDisplayNameResponse
    __check_model__ = False
