# This file has been generated - DO NOT MODIFY
# API Version : 0.3.6


from io import BytesIO, StringIO
from typing import Union

from tenacity import retry, retry_if_result, stop_after_delay, wait_fixed

from avatars.models import (
    CreateDataset,
    CreateUser,
    DatasetResponse,
    ExplainedVariance,
    JobCreate,
    JobResponse,
    JobStatus,
    Login,
    LoginResponse,
    PatchDataset,
    Projections,
)


def _is_job_still_running(response):
    return response.status in (JobStatus.pending, JobStatus.started)


class Auth:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def login(
        self,
        request: Login,
    ) -> LoginResponse:
        """Login the user."""
        kwargs = {
            "method": "post",
            "url": f"/login",
        }
        return LoginResponse(
            **self.client.request(**kwargs, verify_auth=False, form_data=request)
        )


class Datasets:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_dataset(
        self,
        request: Union[StringIO, BytesIO],
    ) -> DatasetResponse:
        """Create a dataset from file upload.

        The file should be in CSV format.
        """
        kwargs = {
            "method": "post",
            "url": f"/datasets",
        }
        return DatasetResponse(**self.client.request(**kwargs, file=request))

    def get_dataset(
        self,
        id: str,
    ) -> DatasetResponse:
        """Get a dataset."""
        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}",
        }
        return DatasetResponse(**self.client.request(**kwargs))

    def patch_dataset(
        self,
        request: PatchDataset,
        id: str,
    ) -> DatasetResponse:
        """Modify a dataset."""
        kwargs = {
            "method": "patch",
            "url": f"/datasets/{id}",
        }
        return DatasetResponse(**self.client.request(**kwargs, json=request))

    def analyze_dataset(
        self,
        id: str,
    ) -> DatasetResponse:
        """Start the analysis of a dataset."""
        kwargs = {
            "method": "post",
            "url": f"/datasets/{id}/analyze",
        }
        return DatasetResponse(**self.client.request(**kwargs))

    def get_dataset_correlations(
        self,
        id: str,
    ) -> None:
        """Get a dataset's correlations."""
        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/correlations",
        }
        return self.client.request(**kwargs)

    def download_dataset(
        self,
        id: str,
    ) -> None:
        """Download a dataset."""
        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/download",
        }
        return self.client.request(**kwargs)


class Health:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_health(
        self,
    ) -> None:
        """Verify server health."""
        kwargs = {
            "method": "get",
            "url": f"/health",
        }
        return self.client.request(**kwargs)

    def get_health_task(
        self,
    ) -> None:
        """Verify async task health."""
        kwargs = {
            "method": "get",
            "url": f"/health/task",
        }
        return self.client.request(**kwargs)

    def get_health_db(
        self,
    ) -> None:
        """Verify connection to the db health."""
        kwargs = {
            "method": "get",
            "url": f"/health/db",
        }
        return self.client.request(**kwargs)


class Jobs:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_job(
        self,
        request: JobCreate,
    ) -> JobResponse:
        kwargs = {
            "method": "post",
            "url": f"/jobs",
        }
        return JobResponse(**self.client.request(**kwargs, json=request))

    @retry(
        stop=stop_after_delay(60),
        wait=wait_fixed(1),
        retry=retry_if_result(_is_job_still_running),
    )
    def get_job(
        self,
        id: str,
    ) -> JobResponse:
        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}",
        }
        return JobResponse(**self.client.request(**kwargs))


class Metrics:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_job_projections(
        self,
        job_id: str,
    ) -> Projections:
        """Get the projections of records and avatars in 3D."""
        kwargs = {
            "method": "get",
            "url": f"/projections/{job_id}",
        }
        return Projections(**self.client.request(**kwargs))

    def get_variable_contributions(
        self,
        job_id: str,
        dataset_id: str,
    ) -> None:
        """Get the contributions of the dataset variables within the fitted space."""
        kwargs = {
            "method": "get",
            "url": f"/contributions",
            "params": dict(
                job_id=job_id,
                dataset_id=dataset_id,
            ),
        }
        return self.client.request(**kwargs)

    def get_explained_variance(
        self,
        job_id: str,
    ) -> ExplainedVariance:
        """Get the explained variance of records."""
        kwargs = {
            "method": "get",
            "url": f"/variance/{job_id}",
        }
        return ExplainedVariance(**self.client.request(**kwargs))


class Users:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def find_users(
        self,
    ) -> None:
        kwargs = {
            "method": "get",
            "url": f"/users",
        }
        return self.client.request(**kwargs)

    def create_user(
        self,
        request: CreateUser,
    ) -> None:
        """Create a user.

        This endpoint is protected with rate limiting.
        """
        kwargs = {
            "method": "post",
            "url": f"/users",
        }
        return self.client.request(**kwargs, json=request)

    def get_me(
        self,
    ) -> None:
        """Get my own user."""
        kwargs = {
            "method": "get",
            "url": f"/users/me",
        }
        return self.client.request(**kwargs)

    def get_user(
        self,
        username: str,
    ) -> None:
        """Get a user."""
        kwargs = {
            "method": "get",
            "url": f"/users/{username}",
        }
        return self.client.request(**kwargs)


# This file has been generated - DO NOT MODIFY
