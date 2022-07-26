# This file has been generated - DO NOT MODIFY
# API Version : 0.4.0


import itertools
import time
from io import BytesIO, StringIO
from typing import Optional, Union

from avatars import client
from avatars.models import (
    ClusterStats,
    CreateDataset,
    CreateUser,
    DatasetResponse,
    ExplainedVariance,
    Job,
    JobCreate,
    JobStatus,
    Login,
    LoginResponse,
    PatchDataset,
    Projections,
)

DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_TIMEOUT = 5


class JobNotFinished(Exception):
    pass


class Auth:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def login(
        self,
        request: Login,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> LoginResponse:
        """Login the user."""
        kwargs = {
            "method": "post",
            "url": f"/login",
        }

        return LoginResponse(
            **self.client.request(
                **kwargs, verify_auth=False, form_data=request, timeout=timeout
            )
        )


class Datasets:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_dataset(
        self,
        request: Union[StringIO, BytesIO],
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> DatasetResponse:
        """Create a dataset from file upload.

        The file should be in CSV format.
        """
        kwargs = {
            "method": "post",
            "url": f"/datasets",
        }

        return DatasetResponse(
            **self.client.request(**kwargs, file=request, timeout=timeout)
        )

    def get_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> DatasetResponse:
        """Get a dataset."""
        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}",
        }

        return DatasetResponse(**self.client.request(**kwargs, timeout=timeout))

    def patch_dataset(
        self,
        request: PatchDataset,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> DatasetResponse:
        """Modify a dataset."""
        kwargs = {
            "method": "patch",
            "url": f"/datasets/{id}",
        }

        return DatasetResponse(
            **self.client.request(**kwargs, json=request, timeout=timeout)
        )

    def analyze_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> DatasetResponse:
        """Start the analysis of a dataset."""
        kwargs = {
            "method": "post",
            "url": f"/datasets/{id}/analyze",
        }

        return DatasetResponse(**self.client.request(**kwargs, timeout=timeout))

    def get_dataset_correlations(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Get a dataset's correlations."""
        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/correlations",
        }
        return self.client.request(**kwargs, timeout=timeout)

    def download_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Download a dataset."""
        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/download",
        }
        return self.client.request(**kwargs, timeout=timeout)


class Health:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_health(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Verify server health."""
        kwargs = {
            "method": "get",
            "url": f"/health",
        }
        return self.client.request(**kwargs, timeout=timeout)

    def get_health_task(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Verify async task health."""
        kwargs = {
            "method": "get",
            "url": f"/health/task",
        }
        return self.client.request(**kwargs, timeout=timeout)

    def get_health_db(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Verify connection to the db health."""
        kwargs = {
            "method": "get",
            "url": f"/health/db",
        }
        return self.client.request(**kwargs, timeout=timeout)


class Jobs:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_job(
        self,
        request: JobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Job:
        """Create a job."""
        kwargs = {
            "method": "post",
            "url": f"/jobs",
        }

        return Job(**self.client.request(**kwargs, json=request, timeout=timeout))

    def get_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Job:
        """Get a job."""
        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}",
        }

        retry_timeout = timeout or DEFAULT_RETRY_TIMEOUT

        start = time.time()
        current = 0

        max_interval = 10
        sleep_interval = iter(
            min(2**i, max_interval) for i in itertools.count()
        )  # Exponential interval, capped at max_interval

        # Iterate while we are < retry_timeout
        while current == 0 or (current < retry_timeout):
            timeout = per_request_timeout  # to pass to client.request
            response = Job(**self.client.request(**kwargs, timeout=timeout))
            if not response.status in (JobStatus.pending, JobStatus.started):
                return response

            # Sleep, but not longer than timeout.
            time_to_sleep = min(next(sleep_interval), retry_timeout - current)
            time.sleep(time_to_sleep)

            current = time.time() - start

        raise JobNotFinished(
            "The job is not yet finished. Call get_job again to retry."
        )


class Metrics:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_job_projections(
        self,
        job_id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Projections:
        """Get the projections of records and avatars in 3D."""
        kwargs = {
            "method": "get",
            "url": f"/projections/{job_id}",
        }

        return Projections(**self.client.request(**kwargs, timeout=timeout))

    def get_variable_contributions(
        self,
        job_id: str,
        dataset_id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
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
        return self.client.request(**kwargs, timeout=timeout)

    def get_explained_variance(
        self,
        job_id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> ExplainedVariance:
        """Get the explained variance of records."""
        kwargs = {
            "method": "get",
            "url": f"/variance/{job_id}",
        }

        return ExplainedVariance(**self.client.request(**kwargs, timeout=timeout))


class Stats:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_cluster_stats(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> ClusterStats:
        """Get insights into the cluster's usage."""
        kwargs = {
            "method": "get",
            "url": f"/stats/cluster",
        }

        return ClusterStats(**self.client.request(**kwargs, timeout=timeout))


class Users:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def find_users(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        kwargs = {
            "method": "get",
            "url": f"/users",
        }
        return self.client.request(**kwargs, timeout=timeout)

    def create_user(
        self,
        request: CreateUser,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Create a user.

        This endpoint is protected with rate limiting.
        """
        kwargs = {
            "method": "post",
            "url": f"/users",
        }
        return self.client.request(**kwargs, json=request, timeout=timeout)

    def get_me(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Get my own user."""
        kwargs = {
            "method": "get",
            "url": f"/users/me",
        }
        return self.client.request(**kwargs, timeout=timeout)

    def get_user(
        self,
        username: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Get a user."""
        kwargs = {
            "method": "get",
            "url": f"/users/{username}",
        }
        return self.client.request(**kwargs, timeout=timeout)


# This file has been generated - DO NOT MODIFY
