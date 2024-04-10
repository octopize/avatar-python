# This file has been generated - DO NOT MODIFY
# API Version : 1.0.0-08a427027c58bf2f64075b929ff63e2d23912ca4


import logging


from avatars.models import AvatarizationBatchJob
from avatars.models import AvatarizationBatchJobCreate
from avatars.models import AvatarizationJob
from avatars.models import AvatarizationJobCreate
from avatars.models import AvatarizationMultiTableJob
from avatars.models import AvatarizationMultiTableJobCreate
from avatars.models import AvatarizationWithTimeSeriesJob
from avatars.models import AvatarizationWithTimeSeriesJobCreate
from avatars.models import ClusterStats
from avatars.models import CompatibilityResponse
from avatars.models import Contributions
from avatars.models import CreateDataset
from avatars.models import CreateUser
from avatars.models import Dataset
from avatars.models import ExplainedVariance
from avatars.models import ForgottenPasswordRequest
from avatars.models import GenericJob
from avatars.models import Login
from avatars.models import LoginResponse
from avatars.models import PatchDataset
from avatars.models import PrivacyMetricsBatchJob
from avatars.models import PrivacyMetricsBatchJobCreate
from avatars.models import PrivacyMetricsGeolocationJob
from avatars.models import PrivacyMetricsGeolocationJobCreate
from avatars.models import PrivacyMetricsJob
from avatars.models import PrivacyMetricsJobCreate
from avatars.models import PrivacyMetricsMultiTableJob
from avatars.models import PrivacyMetricsMultiTableJobCreate
from avatars.models import PrivacyMetricsWithTimeSeriesJob
from avatars.models import PrivacyMetricsWithTimeSeriesJobCreate
from avatars.models import Projections
from avatars.models import Report
from avatars.models import ReportCreate
from avatars.models import ReportFromBatchCreate
from avatars.models import ReportFromDataCreate
from avatars.models import ReportGeolocationPrivacyCreate
from avatars.models import ResetPasswordRequest
from avatars.models import SignalMetricsBatchJob
from avatars.models import SignalMetricsBatchJobCreate
from avatars.models import SignalMetricsJob
from avatars.models import SignalMetricsJobCreate
from avatars.models import SignalMetricsWithTimeSeriesJob
from avatars.models import SignalMetricsWithTimeSeriesJobCreate
from avatars.models import User
from avatars.models import JobStatus, AvatarizationBatchResult
from avatars.models import ColumnDetail, ColumnType
from avatars.models import (
    PrivacyMetrics,
    SignalMetrics,
    PrivacyMetricsParameters,
    SignalMetricsParameters,
)
from avatars.models import (
    Processor,
    AvatarizationPipelineCreate,
    AvatarizationPipelineResult,
)
from avatars.models import FileType

from io import StringIO, BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
    Union,
    List,
    Tuple,
)
from uuid import UUID
import itertools
import time
import pandas as pd
import numpy as np
from pydantic import BaseModel
import pyarrow
from copy import copy

if TYPE_CHECKING:
    from avatars.client import ApiClient


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_TIMEOUT = 60


T = TypeVar("T")


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

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/login",
            "timeout": timeout,
            "form_data": request,
            "should_verify_auth": False,
        }

        return LoginResponse(**self.client.request(**kwargs))

    def forgotten_password(
        self,
        request: ForgottenPasswordRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/login/forgotten_password",
            "timeout": timeout,
            "json_data": request,
            "should_verify_auth": False,
        }

        return self.client.request(**kwargs)

    def reset_password(
        self,
        request: ResetPasswordRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/login/reset_password",
            "timeout": timeout,
            "json_data": request,
            "should_verify_auth": False,
        }

        return self.client.request(**kwargs)


class Compatibility:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def is_client_compatible(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> CompatibilityResponse:
        """Verify if the client is compatible with the API."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/check_client",
            "timeout": timeout,
            "should_verify_auth": False,
        }

        return CompatibilityResponse(**self.client.request(**kwargs))


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

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/datasets/stream",
            "timeout": timeout,
            "params": dict(
                name=name,
            ),
            "file": request,
        }

        return Dataset(**self.client.request(**kwargs))

    def find_all_datasets_by_user(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> List[Dataset]:
        """List all datasets of the current_user."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/datasets",
            "timeout": timeout,
        }

        return [Dataset(**item) for item in self.client.request(**kwargs)]

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

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/datasets",
            "timeout": timeout,
            "file": request,
            "form_data": dict(
                name=name,
            ),
        }

        return Dataset(**self.client.request(**kwargs))

    def get_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Get a dataset."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/datasets/{id}",
            "timeout": timeout,
        }

        return Dataset(**self.client.request(**kwargs))

    def patch_dataset(
        self,
        request: PatchDataset,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Modify a dataset."""

        kwargs: Dict[str, Any] = {
            "method": "patch",
            "url": f"/datasets/{id}",
            "timeout": timeout,
            "json_data": request,
        }

        return Dataset(**self.client.request(**kwargs))

    def analyze_dataset(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Start the analysis of a dataset."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/datasets/{id}/analyze",
            "timeout": timeout,
        }

        return Dataset(**self.client.request(**kwargs))

    def get_dataset_correlations(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Get a dataset's correlations."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/datasets/{id}/correlations",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def download_dataset_as_stream(
        self,
        id: str,
        filetype: Optional[FileType] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Download a dataset by streaming chunks of it."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/datasets/{id}/download/stream",
            "timeout": timeout,
            "params": dict(
                filetype=filetype,
            ),
            "should_stream": True,
        }

        return self.client.request(**kwargs)

    def download_dataset(
        self,
        id: str,
        filetype: Optional[FileType] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Download a dataset."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/datasets/{id}/download",
            "timeout": timeout,
            "params": dict(
                filetype=filetype,
            ),
        }

        return self.client.request(**kwargs)


class Health:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_root(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_health(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/health",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_health_db(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify connection to the db health."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/health/db",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)


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

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs",
            "timeout": timeout,
            "params": dict(
                nb_days=nb_days,
            ),
        }

        return [GenericJob(**item) for item in self.client.request(**kwargs)]

    def create_full_avatarization_job(
        self,
        request: AvatarizationJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationJob:
        """Create an avatarization job, then calculate metrics."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs",
            "timeout": timeout,
            "json_data": request,
        }

        return AvatarizationJob(**self.client.request(**kwargs))

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

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/{id}/cancel",
            "timeout": timeout,
        }

        return GenericJob(**self.client.request(**kwargs))

    def create_avatarization_job(
        self,
        request: AvatarizationJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationJob:
        """Create an avatarization job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/avatarization",
            "timeout": timeout,
            "json_data": request,
        }

        return AvatarizationJob(**self.client.request(**kwargs))

    def create_avatarization_batch_job(
        self,
        request: AvatarizationBatchJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationBatchJob:
        """Create an avatarization batch job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/avatarization_batch",
            "timeout": timeout,
            "json_data": request,
        }

        return AvatarizationBatchJob(**self.client.request(**kwargs))

    def create_avatarization_with_time_series_job(
        self,
        request: AvatarizationWithTimeSeriesJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationWithTimeSeriesJob:
        """Create an avatarization with time series job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/avatarization_with_time_series",
            "timeout": timeout,
            "json_data": request,
        }

        return AvatarizationWithTimeSeriesJob(**self.client.request(**kwargs))

    def create_avatarization_multi_table_job(
        self,
        request: AvatarizationMultiTableJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationMultiTableJob:
        """Create an avatarization for relational data."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/avatarization_multi_table",
            "timeout": timeout,
            "json_data": request,
        }

        return AvatarizationMultiTableJob(**self.client.request(**kwargs))

    def create_signal_metrics_job(
        self,
        request: SignalMetricsJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsJob:
        """Create a signal metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/signal",
            "timeout": timeout,
            "json_data": request,
        }

        return SignalMetricsJob(**self.client.request(**kwargs))

    def create_privacy_metrics_job(
        self,
        request: PrivacyMetricsJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsJob:
        """Create a privacy metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/privacy",
            "timeout": timeout,
            "json_data": request,
        }

        return PrivacyMetricsJob(**self.client.request(**kwargs))

    def create_privacy_metrics_batch_job(
        self,
        request: PrivacyMetricsBatchJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsBatchJob:
        """Create a privacy metrics batch job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_batch",
            "timeout": timeout,
            "json_data": request,
        }

        return PrivacyMetricsBatchJob(**self.client.request(**kwargs))

    def create_privacy_metrics_time_series_job(
        self,
        request: PrivacyMetricsWithTimeSeriesJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsWithTimeSeriesJob:
        """Create a privacy metrics with time series job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_time_series",
            "timeout": timeout,
            "json_data": request,
        }

        return PrivacyMetricsWithTimeSeriesJob(**self.client.request(**kwargs))

    def create_signal_metrics_time_series_job(
        self,
        request: SignalMetricsWithTimeSeriesJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsWithTimeSeriesJob:
        """Create a signal metrics with time series job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/signal_time_series",
            "timeout": timeout,
            "json_data": request,
        }

        return SignalMetricsWithTimeSeriesJob(**self.client.request(**kwargs))

    def create_signal_metrics_batch_job(
        self,
        request: SignalMetricsBatchJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsBatchJob:
        """Create a signal metrics batch job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/signal_batch",
            "timeout": timeout,
            "json_data": request,
        }

        return SignalMetricsBatchJob(**self.client.request(**kwargs))

    def create_privacy_metrics_multi_table_job(
        self,
        request: PrivacyMetricsMultiTableJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsMultiTableJob:
        """Create a privacy metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_multi_table",
            "timeout": timeout,
            "json_data": request,
        }

        return PrivacyMetricsMultiTableJob(**self.client.request(**kwargs))

    def create_privacy_metrics_geolocation_job(
        self,
        request: PrivacyMetricsGeolocationJobCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsGeolocationJob:
        """Create a geolocation privacy metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/metrics/privacy_geolocation",
            "timeout": timeout,
            "json_data": request,
        }

        return PrivacyMetricsGeolocationJob(**self.client.request(**kwargs))

    def get_privacy_metrics_geolocation_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsGeolocationJob:
        """Get a geolocation privacy metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_geolocation",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=PrivacyMetricsGeolocationJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_avatarization_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationJob:
        """Get an avatarization job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/avatarization/{id}",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=AvatarizationJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_avatarization_batch_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationBatchJob:
        """Get an avatarization batch job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/avatarization_batch/{id}",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=AvatarizationBatchJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_avatarization_time_series_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationWithTimeSeriesJob:
        """Get an avatarization time series job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/avatarization_with_time_series/{id}",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=AvatarizationWithTimeSeriesJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_avatarization_multi_table_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> AvatarizationMultiTableJob:
        """Get a multi table avatarization job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/avatarization_multi_table/{id}",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=AvatarizationMultiTableJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_signal_metrics(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsJob:
        """Get a signal metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/signal",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=SignalMetricsJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_signal_metrics_batch_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsBatchJob:
        """Get a signal metrics batch job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/signal_batch",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=SignalMetricsBatchJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_signal_metrics_time_series_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> SignalMetricsWithTimeSeriesJob:
        """Get a signal metrics time series job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/signal_time_series",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=SignalMetricsWithTimeSeriesJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_privacy_metrics(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsJob:
        """Get a privacy metrics job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=PrivacyMetricsJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_privacy_metrics_batch_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsBatchJob:
        """Get a privacy metrics batch job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_batch",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=PrivacyMetricsBatchJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_privacy_metrics_time_series_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsWithTimeSeriesJob:
        """Get a privacy metrics time series job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_time_series",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=PrivacyMetricsWithTimeSeriesJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

    def get_privacy_metrics_multi_table_job(
        self,
        id: str,
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> PrivacyMetricsMultiTableJob:
        """Get a privacy metrics multi table job."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy_multi_table",
            "timeout": timeout,
        }

        return self.client.get_job(
            response_cls=PrivacyMetricsMultiTableJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
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

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/projections/{job_id}",
            "timeout": timeout,
        }

        return Projections(**self.client.request(**kwargs))

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

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/contributions",
            "timeout": timeout,
            "params": dict(
                job_id=job_id,
                dataset_id=dataset_id,
            ),
        }

        return Contributions(**self.client.request(**kwargs))

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

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/variance/{job_id}",
            "timeout": timeout,
        }

        return ExplainedVariance(**self.client.request(**kwargs))


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

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/reports",
            "timeout": timeout,
            "json_data": request,
        }

        return Report(**self.client.request(**kwargs))

    def get_report(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/reports/jobs/{id}",
            "timeout": timeout,
        }

        return Report(**self.client.request(**kwargs))

    def download_report(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Download a report."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/reports/{id}/download",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def create_report_from_data(
        self,
        request: ReportFromDataCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        """Create an anonymization report without avatarization job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/reports/from_data",
            "timeout": timeout,
            "json_data": request,
        }

        return Report(**self.client.request(**kwargs))

    def create_report_from_batch(
        self,
        request: ReportFromBatchCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        """Create an anonymization report from batch job identifiers.

        The report will be generated with the worst privacy_metrics and the mean signal_metrics.
        """

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/reports/from_batch",
            "timeout": timeout,
            "json_data": request,
        }

        return Report(**self.client.request(**kwargs))

    def create_geolocation_privacy_report(
        self,
        request: ReportGeolocationPrivacyCreate,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Report:
        """Create an anonymization report without avatarization job."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/reports/geolocation_privacy",
            "timeout": timeout,
            "json_data": request,
        }

        return Report(**self.client.request(**kwargs))


class Stats:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_cluster_stats(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> ClusterStats:
        """Get insights into the cluster's usage."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/stats/cluster",
            "timeout": timeout,
        }

        return ClusterStats(**self.client.request(**kwargs))


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

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/users",
            "timeout": timeout,
            "params": dict(
                email=email,
                username=username,
            ),
        }

        return [User(**item) for item in self.client.request(**kwargs)]

    def create_user(
        self,
        request: CreateUser,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Create a user.

        This endpoint is protected with rate limiting.
        """

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/users",
            "timeout": timeout,
            "json_data": request,
        }

        return User(**self.client.request(**kwargs))

    def get_me(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Get my own user."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/users/me",
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))

    def get_user(
        self,
        id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Get a user by id.

        This endpoint is protected with rate limiting.
        """

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/users/{id}",
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))
