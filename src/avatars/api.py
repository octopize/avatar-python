# This file has been generated - DO NOT MODIFY
# API Version : 0.20.0


import logging
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypeVar, Union

from avatars.models import (
    CreateDataset,  # noqa: F401
    CreateUser,  # noqa: F401
    CreditsInfo,  # noqa: F401
    FeaturesInfo,  # noqa: F401
    FileAccess,  # noqa: F401
    ForgottenPasswordRequest,  # noqa: F401
    JobCreateRequest,  # noqa: F401
    JobCreateResponse,  # noqa: F401
    JobKind,
    JobResponse,  # noqa: F401
    JobResponseList,  # noqa: F401
    Login,  # noqa: F401
    LoginResponse,  # noqa: F401
    ResetPasswordRequest,  # noqa: F401
    User,  # noqa: F401
)

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
            "url": f"/login",  # noqa: F541
            "timeout": timeout,
            "form_data": request,
            "should_verify_auth": False,
        }

        return LoginResponse(**self.client.request(**kwargs))

    def refresh(
        self,
        token: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> LoginResponse:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/refresh",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                token=token,
            ),
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
            "url": f"/login/forgotten_password",  # noqa: F541
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
            "url": f"/login/reset_password",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
            "should_verify_auth": False,
        }

        return self.client.request(**kwargs)


class Datasets:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def create_dataset(
        self,
        request: Union[StringIO, BytesIO],
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Create a dataset from file upload."""

        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/datasets",  # noqa: F541
            "timeout": timeout,
            "file": request,
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
            "url": f"/",  # noqa: F541
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
            "url": f"/health",  # noqa: F541
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
            "url": f"/health/db",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)


class Jobs:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_jobs(
        self,
        kind: Optional[JobKind] = None,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> JobResponseList:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                kind=kind,
            ),
        }

        return JobResponseList(**self.client.request(**kwargs))

    def create_job(
        self,
        request: JobCreateRequest,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> JobCreateResponse:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/jobs",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return JobCreateResponse(**self.client.request(**kwargs))

    def get_job_status(
        self,
        job_name: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> JobResponse:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{job_name}",  # noqa: F541
            "timeout": timeout,
        }

        return JobResponse(**self.client.request(**kwargs))


class Openapi:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_openapi_schema(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/openapi.json",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)


class Resources:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_user_volume(
        self,
        volume_name: str,
        set_name: str,
        purpose: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/resources/volume",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                volume_name=volume_name,
                set_name=set_name,
                purpose=purpose,
            ),
        }

        return self.client.request(**kwargs)

    def get_resources(
        self,
        set_name: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/resources/{set_name}",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def put_resources(
        self,
        set_name: str,
        yaml_string: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "put",
            "url": f"/resources/{set_name}",  # noqa: F541
            "timeout": timeout,
            "content": yaml_string,
            "headers": {"Content-Type": "application/yaml"},
        }

        return self.client.request(**kwargs)

    def create_resource(
        self,
        set_name: str,
        yaml_string: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/resources/{set_name}",  # noqa: F541
            "timeout": timeout,
            "content": yaml_string,
            "headers": {"Content-Type": "application/yaml"},
        }

        return self.client.request(**kwargs)

    def get_resource(
        self,
        name: str,
        kind: str,
        set_name: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/resources/{set_name}/{name},{kind}",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)


class Results:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_results(
        self,
        job_name: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/results/{job_name}",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_permission_to_download(
        self,
        url: str,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> FileAccess:
        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/access",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                url=url,
            ),
        }

        return FileAccess(**self.client.request(**kwargs))

    def get_upload_url(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        """Get a URL to upload a dataset."""

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/upload_url",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_file(
        self,
        request: FileAccess,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/download",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return self.client.request(**kwargs)


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
            "url": f"/users",  # noqa: F541
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
            "url": f"/users",  # noqa: F541
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
            "url": f"/users/me",  # noqa: F541
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))

    def get_credits_info(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> CreditsInfo:
        """Get the credits info for a user by id.

        This endpoint is protected with rate limiting.
        """

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/users/credits_info",  # noqa: F541
            "timeout": timeout,
        }

        return CreditsInfo(**self.client.request(**kwargs))

    def get_features_info(
        self,
        *,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> FeaturesInfo:
        """Get the list of features for a user.

        This endpoint is protected with rate limiting.
        """

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/users/features_info",  # noqa: F541
            "timeout": timeout,
        }

        return FeaturesInfo(**self.client.request(**kwargs))

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
            "url": f"/users/{id}",  # noqa: F541
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))
