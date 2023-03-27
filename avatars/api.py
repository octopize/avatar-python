# This file has been generated - DO NOT MODIFY
# API Version : 0.5.3


import itertools
import logging
import time
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel

from avatars.models import (
    AvatarizationJob,
    AvatarizationJobCreate,
    AvatarizationPipelineCreate,
    AvatarizationPipelineResult,
    ClusterStats,
    ColumnDetail,
    ColumnType,
    CompatibilityResponse,
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
    PrivacyMetricsJob,
    PrivacyMetricsJobCreate,
    PrivacyMetricsParameters,
    Processor,
    Projections,
    Report,
    ReportCreate,
    ResetPasswordRequest,
    SignalMetrics,
    SignalMetricsJob,
    SignalMetricsJobCreate,
    SignalMetricsParameters,
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
        }
        return LoginResponse(
            **self.client.request(**kwargs, verify_auth=False, form_data=request, timeout=timeout)  # type: ignore[arg-type]
        )

    def forgotten_password(
        self,
        request: ForgottenPasswordRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs = {
            "method": "post",
            "url": f"/login/forgotten_password",
        }
        return self.client.request(**kwargs, verify_auth=False, json=request, timeout=timeout)  # type: ignore[arg-type]

    def reset_password(
        self,
        request: ResetPasswordRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs = {
            "method": "post",
            "url": f"/login/reset_password",
        }
        return self.client.request(**kwargs, verify_auth=False, json=request, timeout=timeout)  # type: ignore[arg-type]


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
        }
        return CompatibilityResponse(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )


class Datasets:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_dataset(
        self,
        request: Union[StringIO, BytesIO],
        *,
        patch: Optional[PatchDataset] = None,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Dataset:
        """Create a dataset from file upload.

        The file should be in CSV format.
        """
        kwargs = {
            "method": "post",
            "url": f"/datasets",
        }
        if patch:
            d = patch.dict()
            types = [("types", e["type"].value) for e in d["columns"]]
            labels = [("labels", e["label"]) for e in d["columns"]]
            params = types + labels
        else:
            params = None

        return Dataset(
            **self.client.request(**kwargs, params=params, file=request, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return Dataset(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return Dataset(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return Dataset(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]

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
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]


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
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]

    def get_health(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""
        kwargs = {
            "method": "get",
            "url": f"/health",
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]

    def get_health_db(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify connection to the db health."""
        kwargs = {
            "method": "get",
            "url": f"/health/db",
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]


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
            "params": dict(
                nb_days=nb_days,
            ),
        }
        return [GenericJob(**item) for item in self.client.request(**kwargs, timeout=timeout)]  # type: ignore[arg-type]

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
        }
        return AvatarizationJob(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return AvatarizationJob(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return get_job(
            client=self.client,
            response_cls=AvatarizationJob,
            per_request_timeout=per_request_timeout,
            timeout=timeout,
            **kwargs,  # type: ignore
        )

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
        }
        return SignalMetricsJob(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return PrivacyMetricsJob(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
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
        }
        return get_job(
            client=self.client,
            response_cls=SignalMetricsJob,
            per_request_timeout=per_request_timeout,
            timeout=timeout,
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
        }
        return get_job(
            client=self.client,
            response_cls=PrivacyMetricsJob,
            per_request_timeout=per_request_timeout,
            timeout=timeout,
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
        """Get the projections of records and avatars in 3D."""
        kwargs = {
            "method": "get",
            "url": f"/projections/{job_id}",
        }
        return Projections(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )

    def get_variable_contributions(
        self,
        job_id: str,
        dataset_id: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Get the contributions of the dataset variables within the fitted space."""
        kwargs = {
            "method": "get",
            "url": f"/contributions",
            "params": dict(
                job_id=job_id,
                dataset_id=dataset_id,
            ),
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]

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
        return ExplainedVariance(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )


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
        }
        return Report(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]


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
        return ClusterStats(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )


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
            "params": dict(
                email=email,
                username=username,
            ),
        }
        return [User(**item) for item in self.client.request(**kwargs, timeout=timeout)]  # type: ignore[arg-type]

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
        }
        return User(
            **self.client.request(**kwargs, json=request, timeout=timeout)  # type: ignore[arg-type]
        )

    def get_me(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> User:
        """Get my own user."""
        kwargs = {
            "method": "get",
            "url": f"/users/me",
        }
        return User(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )

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
        }
        return User(
            **self.client.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
        )


class PandasIntegration:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def upload_dataframe(
        self, request: "pd.DataFrame", *, timeout: Optional[int] = DEFAULT_TIMEOUT
    ) -> Dataset:
        df_types = request.dtypes
        buffer = StringIO()
        request.to_csv(buffer, index=False)
        buffer.seek(0)
        del request

        patch = PatchDataset(
            columns=[
                ColumnDetail(type=to_common_type(str(e)), label=i)
                for i, e in zip(df_types.index, df_types)
            ]
        )
        dataset = self.client.datasets.create_dataset(
            buffer, patch=patch, timeout=timeout
        )

        return dataset

    def download_dataframe(
        self, id: str, *, timeout: Optional[int] = DEFAULT_TIMEOUT
    ) -> pd.DataFrame:
        dataset_info = self.client.datasets.get_dataset(id, timeout=timeout)
        dataset = self.client.datasets.download_dataset(id, timeout=timeout)
        dataset_io = StringIO(dataset)
        dataset_io.seek(0)

        # We apply datetime columns separately as 'datetime' is not a valid pandas dtype
        dtypes = {c.label: c.type.value for c in dataset_info.columns or {}}
        datetime_columns = [
            label for label, type in dtypes.items() if type == ColumnType.datetime.value
        ]

        # Remove datetime columns
        keys = list(dtypes.keys())
        for label in keys:
            if label in datetime_columns:
                dtypes.pop(label, None)

        df = pd.read_csv(dataset_io, dtype=dtypes)

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

        # Calculate signal metrics
        signal_job = self.client.jobs.create_signal_metrics_job(
            SignalMetricsJobCreate(
                parameters=SignalMetricsParameters(
                    original_id=original_dataset_id, avatars_id=unshuffled_dataset.id
                )
            ),
            timeout=per_request_timeout,
        )

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


# This file has been generated - DO NOT MODIFY
