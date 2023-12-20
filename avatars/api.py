# This file has been generated - DO NOT MODIFY
# API Version : 0.5.21-2951c0b68a984332c602f85ddd62dc086790cab4


import itertools
import logging
import time
from copy import copy
from io import BytesIO, StringIO
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)
from uuid import UUID

import numpy as np
import pandas as pd
import pyarrow
from pydantic import BaseModel

from avatars.models import (
    AvatarizationBatchJob,
    AvatarizationBatchJobCreate,
    AvatarizationBatchResult,
    AvatarizationJob,
    AvatarizationJobCreate,
    AvatarizationMultiTableJob,
    AvatarizationMultiTableJobCreate,
    AvatarizationPipelineCreate,
    AvatarizationPipelineResult,
    AvatarizationWithTimeSeriesJob,
    AvatarizationWithTimeSeriesJobCreate,
    ClusterStats,
    ColumnDetail,
    ColumnType,
    CompatibilityResponse,
    Contributions,
    CreateDataset,
    CreateUser,
    Dataset,
    ExplainedVariance,
    ForgottenPasswordRequest,
    GenericJob,
    JobStatus,
    Login,
    LoginResponse,
    PatchDataset,
    PrivacyMetrics,
    PrivacyMetricsBatchJob,
    PrivacyMetricsBatchJobCreate,
    PrivacyMetricsJob,
    PrivacyMetricsJobCreate,
    PrivacyMetricsMultiTableJob,
    PrivacyMetricsMultiTableJobCreate,
    PrivacyMetricsParameters,
    PrivacyMetricsWithTimeSeriesJob,
    PrivacyMetricsWithTimeSeriesJobCreate,
    Processor,
    Projections,
    Report,
    ReportCreate,
    ReportFromBatchCreate,
    ReportFromDataCreate,
    ResetPasswordRequest,
    SignalMetrics,
    SignalMetricsBatchJob,
    SignalMetricsBatchJobCreate,
    SignalMetricsJob,
    SignalMetricsJobCreate,
    SignalMetricsParameters,
    SignalMetricsWithTimeSeriesJob,
    SignalMetricsWithTimeSeriesJobCreate,
    User,
)

if TYPE_CHECKING:
    from avatars.client import ApiClient


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_TIMEOUT = 5


class FileTooLarge(Exception):
    pass


class Timeout(Exception):
    pass


T = TypeVar("T")


def to_common_type(s: str) -> ColumnType:
    if "float" in s:
        return ColumnType.float
    if "int" in s:
        return ColumnType.int
    if "bool" in s:
        return ColumnType.bool
    if "datetime" in s:
        return ColumnType.datetime
    if "object" in s or s == "category" or s == "str":
        return ColumnType.category
    raise TypeError(f"Unknown column type: '{s}'")


def get_job(
    client: "ApiClient",
    response_cls: Callable[..., T],
    *,
    per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
    timeout: Optional[int] = DEFAULT_TIMEOUT,
    **kwargs: Dict[str, Any],
) -> T:
    def print_response(job_response: Any) -> None:
        if not job_response.current_progress:
            return
        message = f"[{job_response.current_progress.created_at.time()}] Status: {job_response.status}, current_step: {job_response.current_progress.name}"
        logger.info(message)

    retry_timeout = timeout or DEFAULT_RETRY_TIMEOUT

    start = time.time()
    current: float = 0

    max_interval = 10
    # Exponential interval, capped at max_interval
    sleep_interval = iter(min(2**i, max_interval) for i in itertools.count())

    # Iterate while we are < retry_timeout
    while current == 0 or (current < retry_timeout):
        timeout = per_request_timeout  # to pass to client.request
        response = response_cls(**client.request(**kwargs, timeout=timeout))  # type: ignore[arg-type]
        if response.status not in (JobStatus.pending, JobStatus.started):  # type: ignore[attr-defined]
            print_response(response)
            return response

        print_response(response)

        # Sleep, but not longer than timeout
        time_to_sleep = min(next(sleep_interval), retry_timeout - current)
        time.sleep(time_to_sleep)

        current = time.time() - start

    return response


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
            "timeout": timeout,
            "form_data": request,
            "verify_auth": False,
        }

        return LoginResponse(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def forgotten_password(
        self,
        request: ForgottenPasswordRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs = {
            "method": "post",
            "url": f"/login/forgotten_password",
            "timeout": timeout,
            "json": request,
            "verify_auth": False,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]

    def reset_password(
        self,
        request: ResetPasswordRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs = {
            "method": "post",
            "url": f"/login/reset_password",
            "timeout": timeout,
            "json": request,
            "verify_auth": False,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]


class Compatibility:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def is_client_compatible(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> CompatibilityResponse:
        """Verify if the client is compatible with the API."""

        kwargs = {
            "method": "get",
            "url": f"/check_client",
            "timeout": timeout,
            "verify_auth": False,
        }

        return CompatibilityResponse(**self.client.request(**kwargs))  # type: ignore[arg-type]


class Datasets:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_dataset_from_stream(
        self,
        request: Union[StringIO, BytesIO],
        name: Optional[str] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Create a dataset by streaming chunks of the dataset."""

        kwargs = {
            "method": "post",
            "url": f"/datasets/stream",
            "timeout": timeout,
            "params": dict(
                name=name,
            ),
            "file": request,
        }

        return Dataset(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def find_all_datasets_by_user(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> List[Dataset]:
        """List all datasets of the current_user."""

        kwargs = {
            "method": "get",
            "url": f"/datasets",
            "timeout": timeout,
        }

        return [Dataset(**item) for item in self.client.request(**kwargs)]  # type: ignore[arg-type]

    def create_dataset(
        self,
        request: Union[StringIO, BytesIO],
        name: Optional[str] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Create a dataset from file upload.

        The file should be in CSV format.
        """

        kwargs = {
            "method": "post",
            "url": f"/datasets",
            "timeout": timeout,
            "file": request,
            "form_data": dict(
                name=name,
            ),
        }

        return Dataset(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Get a dataset."""

        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}",
            "timeout": timeout,
        }

        return Dataset(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def patch_dataset(
        self,
        request: PatchDataset,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Modify a dataset."""

        kwargs = {
            "method": "patch",
            "url": f"/datasets/{id}",
            "timeout": timeout,
            "json": request,
        }

        return Dataset(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def analyze_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Start the analysis of a dataset."""

        kwargs = {
            "method": "post",
            "url": f"/datasets/{id}/analyze",
            "timeout": timeout,
        }

        return Dataset(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_dataset_correlations(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Get a dataset's correlations."""

        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/correlations",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]

    def download_dataset_as_stream(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Download a dataset by streaming chunks of it."""

        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/download/stream",
            "timeout": timeout,
            "should_stream": True,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]

    def download_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Download a dataset."""

        kwargs = {
            "method": "get",
            "url": f"/datasets/{id}/download",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]


class Health:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_root(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""

        kwargs = {
            "method": "get",
            "url": f"/",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]

    def get_health(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""

        kwargs = {
            "method": "get",
            "url": f"/health",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]

    def get_health_db(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify connection to the db health."""

        kwargs = {
            "method": "get",
            "url": f"/health/db",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]


class Jobs:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def find_all_jobs_by_user(
        self,
        nb_days: Optional[int] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> List[GenericJob]:
        """Retrieve all jobs executed by the current user.

        Jobs are filtered by execution date, by default only the last 5 days are displayed,
        a parameter can be provided to go further back in time.
        """

        kwargs = {
            "method": "get",
            "url": f"/jobs",
            "timeout": timeout,
            "params": dict(
                nb_days=nb_days,
            ),
        }

        return [GenericJob(**item) for item in self.client.request(**kwargs)]  # type: ignore[arg-type]

    def create_full_avatarization_job(
        self,
        request: AvatarizationJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationJob:
        """Create an avatarization job, then calculate metrics."""

        kwargs = {
            "method": "post",
            "url": f"/jobs",
            "timeout": timeout,
            "json": request,
        }

        return AvatarizationJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def cancel_job(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> GenericJob:
        """Cancel any kind of job.

        If the job hadn't been started yet, revoke it.
        If the job is ongoing, gently kill it.
        If the job is done, do nothing.
        """

        kwargs = {
            "method": "post",
            "url": f"/jobs/{id}/cancel",
            "timeout": timeout,
        }

        return GenericJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_avatarization_job(
        self,
        request: AvatarizationJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationJob:
        """Create an avatarization job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/avatarization",
            "timeout": timeout,
            "json": request,
        }

        return AvatarizationJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_avatarization_batch_job(
        self,
        request: AvatarizationBatchJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationBatchJob:
        """Create an avatarization batch job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/avatarization_batch",
            "timeout": timeout,
            "json": request,
        }

        return AvatarizationBatchJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_avatarization_with_time_series_job(
        self,
        request: AvatarizationWithTimeSeriesJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationWithTimeSeriesJob:
        """Create an avatarization with time series job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/avatarization_with_time_series",
            "timeout": timeout,
            "json": request,
        }

        return AvatarizationWithTimeSeriesJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_avatarization_multi_table_job(
        self,
        request: AvatarizationMultiTableJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationMultiTableJob:
        """Create an avatarization for relational data."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/avatarization_multi_table",
            "timeout": timeout,
            "json": request,
        }

        return AvatarizationMultiTableJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_signal_metrics_job(
        self,
        request: SignalMetricsJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsJob:
        """Create a signal metrics job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/signal",
            "timeout": timeout,
            "json": request,
        }

        return SignalMetricsJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_privacy_metrics_job(
        self,
        request: PrivacyMetricsJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsJob:
        """Create a privacy metrics job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/privacy",
            "timeout": timeout,
            "json": request,
        }

        return PrivacyMetricsJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_privacy_metrics_batch_job(
        self,
        request: PrivacyMetricsBatchJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsBatchJob:
        """Create a privacy metrics batch job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_batch",
            "timeout": timeout,
            "json": request,
        }

        return PrivacyMetricsBatchJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_privacy_metrics_time_series_job(
        self,
        request: PrivacyMetricsWithTimeSeriesJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsWithTimeSeriesJob:
        """Create a privacy metrics with time series job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_time_series",
            "timeout": timeout,
            "json": request,
        }

        return PrivacyMetricsWithTimeSeriesJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_signal_metrics_time_series_job(
        self,
        request: SignalMetricsWithTimeSeriesJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsWithTimeSeriesJob:
        """Create a signal metrics with time series job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/signal_time_series",
            "timeout": timeout,
            "json": request,
        }

        return SignalMetricsWithTimeSeriesJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_signal_metrics_batch_job(
        self,
        request: SignalMetricsBatchJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsBatchJob:
        """Create a signal metrics batch job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/signal_batch",
            "timeout": timeout,
            "json": request,
        }

        return SignalMetricsBatchJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_privacy_metrics_multi_table_job(
        self,
        request: PrivacyMetricsMultiTableJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsMultiTableJob:
        """Create a privacy metrics job."""

        kwargs = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_multi_table",
            "timeout": timeout,
            "json": request,
        }

        return PrivacyMetricsMultiTableJob(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_avatarization_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationJob:
        """Get an avatarization job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/avatarization/{id}",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=AvatarizationJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_avatarization_batch_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationBatchJob:
        """Get an avatarization batch job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/avatarization_batch/{id}",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=AvatarizationBatchJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_avatarization_time_series_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationWithTimeSeriesJob:
        """Get an avatarization time series job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/avatarization_with_time_series/{id}",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=AvatarizationWithTimeSeriesJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_avatarization_multi_table_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationMultiTableJob:
        """Get a multi table avatarization job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/avatarization_multi_table/{id}",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=AvatarizationMultiTableJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_signal_metrics(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsJob:
        """Get a signal metrics job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/signal",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=SignalMetricsJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_signal_metrics_batch_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsBatchJob:
        """Get a signal metrics batch job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/signal_batch",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=SignalMetricsBatchJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_signal_metrics_time_series_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsWithTimeSeriesJob:
        """Get a signal metrics time series job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/signal_time_series",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=SignalMetricsWithTimeSeriesJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_privacy_metrics(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsJob:
        """Get a privacy metrics job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=PrivacyMetricsJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_privacy_metrics_batch_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsBatchJob:
        """Get a privacy metrics batch job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_batch",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=PrivacyMetricsBatchJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_privacy_metrics_time_series_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsWithTimeSeriesJob:
        """Get a privacy metrics time series job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_time_series",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=PrivacyMetricsWithTimeSeriesJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
        )

    def get_privacy_metrics_multi_table_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsMultiTableJob:
        """Get a privacy metrics multi table job."""

        kwargs = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_multi_table",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=PrivacyMetricsMultiTableJob,
            per_request_timeout=per_request_timeout,
            **kwargs,  # type: ignore
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
        """Get the projections of records and avatars in 3D.

        See https://saiph.readthedocs.io/en/latest/ for more information.

        Arguments
        ---------
            job_id:
                avatarization or privacy job id used to fit the model
        """

        kwargs = {
            "method": "get",
            "url": f"/projections/{job_id}",
            "timeout": timeout,
        }

        return Projections(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_variable_contributions(
        self,
        job_id: str,
        dataset_id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Contributions:
        """Get the contributions of the dataset variables within the fitted space.

        See https://saiph.readthedocs.io/en/latest for more information.

        Arguments
        ---------
            job_id:
                avatarization or privacy job id used to fit the model
        """

        kwargs = {
            "method": "get",
            "url": f"/contributions",
            "timeout": timeout,
            "params": dict(
                job_id=job_id,
                dataset_id=dataset_id,
            ),
        }

        return Contributions(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_explained_variance(
        self,
        job_id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> ExplainedVariance:
        """Get the explained variance of records.

        See https://saiph.readthedocs.io/en/latest/ for more information.

        Arguments
        ---------
            job_id:
                avatarization or privacy job id used to fit the model
        """

        kwargs = {
            "method": "get",
            "url": f"/variance/{job_id}",
            "timeout": timeout,
        }

        return ExplainedVariance(**self.client.request(**kwargs))  # type: ignore[arg-type]


class Reports:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_report(
        self,
        request: ReportCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        """Create an anonymization report."""

        kwargs = {
            "method": "post",
            "url": f"/reports",
            "timeout": timeout,
            "json": request,
        }

        return Report(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def download_report(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Download a report."""

        kwargs = {
            "method": "get",
            "url": f"/reports/{id}/download",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)  # type: ignore[arg-type]

    def create_report_from_data(
        self,
        request: ReportFromDataCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        """Create an anonymization report without avatarization job."""

        kwargs = {
            "method": "post",
            "url": f"/reports/from_data",
            "timeout": timeout,
            "json": request,
        }

        return Report(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def create_report_from_batch(
        self,
        request: ReportFromBatchCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        """Create an anonymization report from batch job identifiers.

        The report will be generated with the worst privacy_metrics and the mean signal_metrics.
        """

        kwargs = {
            "method": "post",
            "url": f"/reports/from_batch",
            "timeout": timeout,
            "json": request,
        }

        return Report(**self.client.request(**kwargs))  # type: ignore[arg-type]


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
            "timeout": timeout,
        }

        return ClusterStats(**self.client.request(**kwargs))  # type: ignore[arg-type]


class Users:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def find_users(
        self,
        email: Optional[str] = None,
        username: Optional[str] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> List[User]:
        """Get users, optionally filtering them by username or email.

        This endpoint is protected with rate limiting.
        """

        kwargs = {
            "method": "get",
            "url": f"/users",
            "timeout": timeout,
            "params": dict(
                email=email,
                username=username,
            ),
        }

        return [User(**item) for item in self.client.request(**kwargs)]  # type: ignore[arg-type]

    def create_user(
        self,
        request: CreateUser,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Create a user.

        This endpoint is protected with rate limiting.
        """

        kwargs = {
            "method": "post",
            "url": f"/users",
            "timeout": timeout,
            "json": request,
        }

        return User(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_me(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Get my own user."""

        kwargs = {
            "method": "get",
            "url": f"/users/me",
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))  # type: ignore[arg-type]

    def get_user(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Get a user by id.

        This endpoint is protected with rate limiting.
        """

        kwargs = {
            "method": "get",
            "url": f"/users/{id}",
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))  # type: ignore[arg-type]


class PandasIntegration:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def upload_dataframe(
        self,
        request: "pd.DataFrame",
        name: Optional[str] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        should_stream: bool = False,
        identifier_variables: List[str] = [],
    ) -> Dataset:
        for col in request.columns:
            if pd.api.types.infer_dtype(request[col], skipna=True) in (
                "mixed-integer",
                "mixed",
            ):
                raise ValueError(
                    f"Expected column '{col}' should have either str or numeric values."
                    " Consider harmonizing columns prior to upload."
                )

        df_types = request.dtypes
        buffer = BytesIO()
        request.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)
        del request

        if should_stream:
            dataset = self.client.datasets.create_dataset_from_stream(
                buffer, timeout=timeout, name=name
            )
        else:
            dataset = self.client.datasets.create_dataset(
                buffer, timeout=timeout, name=name
            )
            columns = []
            for index, dtype in zip(df_types.index, df_types):
                if index in identifier_variables:
                    column_detail = ColumnDetail(
                        type=ColumnType.identifier, label=index
                    )
                else:
                    column_detail = ColumnDetail(
                        type=to_common_type(str(dtype)), label=index
                    )
                columns.append(column_detail)

            dataset = self.client.datasets.patch_dataset(
                id=str(dataset.id),
                request=PatchDataset(columns=columns),
            )
        return dataset

    def download_dataframe(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        should_stream: bool = False,
    ) -> pd.DataFrame:
        dataset_info = self.client.datasets.get_dataset(id, timeout=timeout)
        dataset_io: BytesIO
        if should_stream:
            dataset_io = self.client.datasets.download_dataset_as_stream(
                id, timeout=timeout
            )
        else:
            dataset = self.client.datasets.download_dataset(id, timeout=timeout)
            dataset_io = BytesIO(
                dataset.encode("utf-8") if isinstance(dataset, str) else dataset
            )

        dataset_io.seek(0)

        # We apply datetime columns separately as 'datetime' is not a valid pandas dtype
        dtypes = {
            c.label: c.type.value
            for c in dataset_info.columns or {}
            if c.type is not ColumnType.identifier
        }
        datetime_columns = [
            label for label, type in dtypes.items() if type == ColumnType.datetime.value
        ]

        # Remove datetime columns
        for label in list(dtypes.keys()):
            if label in datetime_columns:
                dtypes.pop(label, None)
        try:
            # We do copy() because read_parquet consumes the buffer, even on failure.
            df = pd.read_parquet(copy(dataset_io), engine="pyarrow")
        except pyarrow.lib.ArrowInvalid as e:
            if (
                not "Either the file is corrupted or this is not a parquet file."
                in str(e.args)
            ):
                raise e
            df = pd.read_csv(dataset_io)

        for name, dtype in dtypes.items():
            df[name] = df[name].astype(dtype)

        df[datetime_columns] = df[datetime_columns].astype("datetime64[ns]")

        return df


class Pipelines:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def avatarization_pipeline_with_processors(
        self,
        request: AvatarizationPipelineCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationPipelineResult:
        """Create a Pipeline of avatarization with processors."""

        # Upload the dataset if needed
        # User can either specify the dataset he already uploaded or let this pipeline upload it
        df = request.df.copy()
        original_dataset_id = (
            request.avatarization_job_create.parameters.dataset_id
            or self.client.pandas_integration.upload_dataframe(df, timeout=timeout).id
        )

        # Pre process the dataframe and upload it
        processors = request.processors
        for p in processors:
            df = p.preprocess(df)
        dataset = self.client.pandas_integration.upload_dataframe(
            df, timeout=per_request_timeout
        )

        # Avatarize the uploaded dataframe
        request.avatarization_job_create.parameters.dataset_id = dataset.id
        avatarization_job = self.client.jobs.create_avatarization_job(
            request.avatarization_job_create
        )
        print(f"launching avatarization job with id={avatarization_job.id}")

        avatarization_job = self.client.jobs.get_avatarization_job(
            str(avatarization_job.id),
            timeout=timeout,
            per_request_timeout=per_request_timeout,
        )
        if avatarization_job.status == JobStatus.failure:
            raise Exception(
                f"Got error during the avatarization job: {avatarization_job.error_message}"
            )

        if (
            avatarization_job.status == JobStatus.pending
            or not avatarization_job.result
        ):
            raise Timeout(
                f"The avatarization job '{avatarization_job.id}' timed out."
                ""
                """Try increasing the timeout with the `timeout` parameter."""
            )

        # Download the dataframe, postprocess it and upload the new dataframe
        sensitive_unshuffled_avatars = (
            self.client.pandas_integration.download_dataframe(
                str(avatarization_job.result.sensitive_unshuffled_avatars_datasets.id),
                timeout=timeout,
            )
        )
        for p in reversed(processors):
            sensitive_unshuffled_avatars = p.postprocess(
                request.df, sensitive_unshuffled_avatars
            )
        unshuffled_dataset = self.client.pandas_integration.upload_dataframe(
            sensitive_unshuffled_avatars, timeout=timeout
        )

        # Calculate privacy metrics on the post processed dataset vs the original one
        privacy_job = self.client.jobs.create_privacy_metrics_job(
            PrivacyMetricsJobCreate(
                parameters=PrivacyMetricsParameters(
                    original_id=original_dataset_id,
                    unshuffled_avatars_id=unshuffled_dataset.id,
                )
            ),
            timeout=per_request_timeout,
        )
        print(f"launching privacy metrics job with id={privacy_job.id}")

        # Calculate signal metrics
        signal_job = self.client.jobs.create_signal_metrics_job(
            SignalMetricsJobCreate(
                parameters=SignalMetricsParameters(
                    original_id=original_dataset_id, avatars_id=unshuffled_dataset.id
                )
            ),
            timeout=per_request_timeout,
        )
        print(f"launching signal metrics job with id={signal_job.id}")

        # Get the job results
        signal_job = self.client.jobs.get_signal_metrics(
            str(signal_job.id), timeout=timeout, per_request_timeout=per_request_timeout
        )
        privacy_job = self.client.jobs.get_privacy_metrics(
            str(privacy_job.id),
            timeout=timeout,
            per_request_timeout=per_request_timeout,
        )
        if signal_job.status == JobStatus.failure:
            raise Exception(
                f"Got error during the signal metrics job: {signal_job.error_message}"
            )
        if privacy_job.status == JobStatus.failure:
            raise Exception(
                f"Got error during the privacy metrics job: {privacy_job.error_message}"
            )

        if signal_job.status == JobStatus.pending or not signal_job.result:
            raise Timeout(
                f"The signal metrics job '{signal_job.id}' timed out."
                ""
                """Try increasing the timeout with the `timeout` parameter."""
            )

        if privacy_job.status == JobStatus.pending or not privacy_job.result:
            raise Timeout(
                f"The privacy metrics job '{privacy_job.id}' timed out."
                ""
                """Try increasing the timeout with the `timeout` parameter."""
            )

        # Shuffle sensitive_unshuffled_avatars for security reasons
        random_gen = np.random.default_rng()
        map = random_gen.permutation(sensitive_unshuffled_avatars.index.values).tolist()
        post_processed_avatars = sensitive_unshuffled_avatars.iloc[map].reset_index(
            drop=True
        )

        return AvatarizationPipelineResult(
            privacy_metrics=privacy_job.result,
            signal_metrics=signal_job.result,
            post_processed_avatars=post_processed_avatars,
            avatarization_job_id=avatarization_job.id,
            signal_job_id=signal_job.id,
            privacy_job_id=privacy_job.id,
        )


def upload_batch_and_get_order(
    client: "ApiClient",
    training: pd.DataFrame,
    splits: List[pd.DataFrame],
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[UUID, List[UUID], Dict[UUID, pd.Index]]:
    """Upload batches to the server
    Arguments
    ---------
        client:
            Api client
        training:
            Dataframe used to train the anonymization model. This dataframe should contain all modalities of the categorical variables.
        splits:
            All other batches
    Returns
    -------
        training_dataset_id:
            The dataset id of the training dataset
        datasets_split_ids:
            The dataset id of all other batches
        batch_mapping:
            The index mapping for each dataset batch
    """
    training_dataset = client.pandas_integration.upload_dataframe(
        training, timeout=timeout
    )

    datasets_split_ids = [
        client.pandas_integration.upload_dataframe(split, timeout=timeout).id
        for split in splits
    ]
    batch_mapping: Dict[UUID, pd.Index] = {training_dataset.id: training.index}
    for dataset, dataframe in zip(datasets_split_ids, splits):
        batch_mapping[dataset] = dataframe.index

    return training_dataset.id, datasets_split_ids, batch_mapping


def download_avatar_dataframe_from_batch(
    client: "ApiClient",
    avatarization_batch_result: AvatarizationBatchResult,
    timeout: int = DEFAULT_TIMEOUT,
) -> pd.DataFrame:
    """Download the shuffled avatar dataframe from batch result.
    Arguments
    ---------
        client:
            Api client
        avatarization_batch_result:
            Result of the batch avatarization
    Returns
    -------
        the concatenated shuffled avatar dataframe
    """
    training_df = client.pandas_integration.download_dataframe(
        str(avatarization_batch_result.training_result.avatars_dataset.id),
        timeout=timeout,
    )
    splits_df = [
        client.pandas_integration.download_dataframe(
            str(batch_results.avatars_dataset.id),
            timeout=timeout,
        )
        for batch_results in avatarization_batch_result.batch_results
    ]
    return pd.concat([training_df] + splits_df)


def download_sensitive_unshuffled_avatar_dataframe_from_batch(
    client: "ApiClient",
    avatarization_batch_result: AvatarizationBatchResult,
    order: Dict[UUID, pd.Index],
    timeout: int = DEFAULT_TIMEOUT,
) -> pd.DataFrame:
    """Download the sensitive unshuffled avatar dataframe from batch result.

    The avatar dataframe is ordered in the original dataframe order.
    Arguments
    ---------
        client:
            Api client
        avatarization_batch_result:
            Result of the batch avatarization
        order:
            index order for each dataset batch
    Returns
    -------
        concatenated:
            the concatenated avatar dataframe with the row order of the original dataframe
    """
    avatar_training_id = (
        avatarization_batch_result.training_result.sensitive_unshuffled_avatars_datasets.id
    )
    original_training_id = avatarization_batch_result.training_result.original_id
    training_df = client.pandas_integration.download_dataframe(
        str(avatar_training_id), timeout=timeout
    )
    training_df.index = order[original_training_id]

    split_dfs = []
    for batch_results in avatarization_batch_result.batch_results:
        avatar_dataset_id = batch_results.sensitive_unshuffled_avatars_datasets.id
        original_dataset_id = batch_results.original_id

        split = client.pandas_integration.download_dataframe(
            str(avatar_dataset_id), timeout=timeout
        )
        split.index = order[original_dataset_id]
        split_dfs.append(split)

    concatenated = pd.concat([training_df] + split_dfs).sort_index()
    return concatenated


# This file has been generated - DO NOT MODIFY
