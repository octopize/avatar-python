# This file has been generated - DO NOT MODIFY
# API Version : 3.6.0


import logging
from typing import TYPE_CHECKING, Any, TypeVar

from avatars.models import (
    ApiKey,
    BulkDeleteRequest,
    BulkDeleteResponse,
    CompatibilityResponse,
    CreateApiKeyRequest,
    CreditsInfo,
    EventLogResponse,
    FeaturesInfo,
    FileAccess,
    JobCreateRequest,
    JobCreateResponse,
    JobKind,
    JobResponse,
    JobResponseList,
    MeUser,
    ResourceSetResponse,
    User,
)

if TYPE_CHECKING:
    from avatars.client import ApiClient


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
DEFAULT_TIMEOUT = 60


T = TypeVar("T")


class ApiKeys:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def list_api_keys(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> list[ApiKey]:
        """List all API keys for the authenticated user.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/api-keys",  # noqa: F541
            "timeout": timeout,
        }

        return [ApiKey(**item) for item in self.client.request(**kwargs)]

    def create_api_key(
        self,
        request: CreateApiKeyRequest,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Create a new API key for the authenticated user.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/api-keys",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return self.client.request(**kwargs)

    def revoke_all_api_keys(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Revoke all API keys for the authenticated user.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "delete",
            "url": f"/api-keys",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_api_key(
        self,
        api_key_id: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ApiKey:
        """Get details of a specific API key.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/api-keys/{api_key_id}",
            "timeout": timeout,
        }

        return ApiKey(**self.client.request(**kwargs))

    def revoke_api_key(
        self,
        api_key_id: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Revoke a specific API key.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "delete",
            "url": f"/api-keys/{api_key_id}",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def revoke_api_key_admin(
        self,
        user_id: str | None = None,
        api_key_id: str | None = None,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Revoke API key(s) for another user (admin only).

        Accepts either:
        - user_id: Revoke all API keys for the specified user
        - api_key_id: Revoke a specific API key

        This endpoint requires admin permissions and is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "delete",
            "url": f"/api-keys/admin",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                user_id=user_id,
                api_key_id=api_key_id,
            ),
        }

        return self.client.request(**kwargs)


class Compatibility:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def is_client_compatible(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> CompatibilityResponse:
        """Verify if the client is compatible with the API."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/check_client",  # noqa: F541
            "timeout": timeout,
            "should_verify_auth": False,
        }

        return CompatibilityResponse(**self.client.request(**kwargs))


class EventLogs:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def list_my_event_logs(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> list[EventLogResponse]:
        """Return the audit trail for the authenticated user, most recent first."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/event-logs",  # noqa: F541
            "timeout": timeout,
        }

        return [EventLogResponse(**item) for item in self.client.request(**kwargs)]


class Health:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_root(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_health(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify server health."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/health",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_health_db(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Verify connection to the db health."""
        kwargs: dict[str, Any] = {
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
        kind: list[JobKind] | None = None,
        display_name: str | None = None,
        set_name: str | None = None,
        limit: int | None = None,
        include_deleted: bool | None = None,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobResponseList:

        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/jobs",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                kind=kind,
                display_name=display_name,
                set_name=set_name,
                limit=limit,
                include_deleted=include_deleted,
            ),
        }

        return JobResponseList(**self.client.request(**kwargs))

    def create_job(
        self,
        request: JobCreateRequest,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobCreateResponse:

        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/jobs",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return JobCreateResponse(**self.client.request(**kwargs))

    def get_last_jobs(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobResponseList:
        """Return all jobs belonging to the set_name that was most recently created."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/last_set",  # noqa: F541
            "timeout": timeout,
        }

        return JobResponseList(**self.client.request(**kwargs))

    def get_job_status(
        self,
        job_name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobResponse:

        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{job_name}",
            "timeout": timeout,
        }

        return JobResponse(**self.client.request(**kwargs))

    def delete_job(
        self,
        job_name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobResponse:
        """Delete a single job by name."""
        kwargs: dict[str, Any] = {
            "method": "delete",
            "url": f"/jobs/{job_name}",
            "timeout": timeout,
        }

        return JobResponse(**self.client.request(**kwargs))

    def bulk_delete_jobs(
        self,
        request: BulkDeleteRequest,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> BulkDeleteResponse:
        """Delete multiple jobs in a single request. Maximum 100 jobs at once."""
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/bulk-delete",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return BulkDeleteResponse(**self.client.request(**kwargs))


class Openapi:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_openapi_schema(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:

        kwargs: dict[str, Any] = {
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
        purpose: str,
        set_name: str | None = None,
        display_name: str | None = None,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Generate a user volume configuration for a resource set.

        Creates a volume configuration YAML that can be used to mount user data
        or results for Avatar processing jobs. The volume references a specific
        resource set by display name.

        Args:
            volume_name: Name for the generated volume configuration
            set_name: UUID of the resource set to create volume for (required)
            purpose: Whether this volume is for "input" data or "results" output
            user: Current authenticated user
            display_name: [DEPRECATED] Use set_name instead. For backward compatibility only.

        Returns:
            Plain text response containing the volume configuration YAML

        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/resources/volume",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                volume_name=volume_name,
                purpose=purpose,
                set_name=set_name,
                display_name=display_name,
            ),
        }

        return self.client.request(**kwargs)

    def get_resources(
        self,
        set_name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Retrieve all resources from a resource set.

        Returns all resources in a resource set as YAML content. The set is
        identified by its UUID.

        Args:
            user: Current authenticated user
            set_name: UUID of the resource set to retrieve

        Returns:
            YamlResponse containing all resources in the set as YAML

        Raises:
            HTTPException: 404 if the resource set does not exist

        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/resources/{set_name}",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def create_resource(
        self,
        set_name: str,
        yaml_string: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ResourceSetResponse:
        """Add new resources to an existing resource set.

        Adds resources defined in YAML format to a resource set identified by UUID.
        The resource set must already exist. This endpoint appends to existing
        resources rather than replacing them.

        Args:
            user: Current authenticated user
            set_name: UUID of the resource set to add to
            yaml: YAML content defining the resources to add

        Returns:
            ResourceSetResponse containing the set UUID and display name

        Raises:
            HTTPException: 404 if the resource set does not exist

        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/resources/{set_name}",
            "timeout": timeout,
            "content": yaml_string,
            "headers": {"Content-Type": "application/yaml"},
        }

        return ResourceSetResponse(**self.client.request(**kwargs))

    def put_resources(
        self,
        display_name: str,
        yaml_string: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ResourceSetResponse:
        """Create a new version of a resource set with complete replacement.

        Creates a brand new resource set with a fresh UUID, replacing all resources
        with the provided YAML content. This implements versioning - the old set
        remains unchanged while a new version is created with the same display name.

        Args:
            user: Current authenticated user
            display_name: Human-readable name for the resource set (preserved across versions)
            yaml: YAML content defining all resources for the new version

        Returns:
            ResourceSetResponse with the new UUID and the same display name

        """
        kwargs: dict[str, Any] = {
            "method": "put",
            "url": f"/resources/{display_name}",
            "timeout": timeout,
            "content": yaml_string,
            "headers": {"Content-Type": "application/yaml"},
        }

        return ResourceSetResponse(**self.client.request(**kwargs))


class Results:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_results(
        self,
        job_name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:

        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/results/{job_name}",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def get_permission_to_download(
        self,
        url: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> FileAccess:

        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/access",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                url=url,
            ),
        }

        return FileAccess(**self.client.request(**kwargs))

    def get_permissions_to_download_batch(
        self,
        urls: list[str],
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> list[FileAccess]:
        """Get permissions for multiple files at once.

        Files that fail permission checks are silently skipped rather than
        causing the entire batch to fail.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/access/batch",  # noqa: F541
            "timeout": timeout,
            "json_data": urls,
        }

        return [FileAccess(**item) for item in self.client.request(**kwargs)]

    def get_upload_url(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Get a URL to upload a dataset."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/upload_url",  # noqa: F541
            "timeout": timeout,
        }

        return self.client.request(**kwargs)


class Users:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_me(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> MeUser:
        """Get my own user."""
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/users/me",  # noqa: F541
            "timeout": timeout,
        }

        return MeUser(**self.client.request(**kwargs))

    def find_users(
        self,
        email: str | None = None,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> list[User]:
        """Get users, optionally filtering them by email.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/users",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                email=email,
            ),
        }

        return [User(**item) for item in self.client.request(**kwargs)]

    def get_credits_info(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> CreditsInfo:
        """Get the credits info for a user by id.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/users/credits_info",  # noqa: F541
            "timeout": timeout,
        }

        return CreditsInfo(**self.client.request(**kwargs))

    def get_features_info(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> FeaturesInfo:
        """Get the list of features for a user.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/users/features_info",  # noqa: F541
            "timeout": timeout,
        }

        return FeaturesInfo(**self.client.request(**kwargs))

    def get_user(
        self,
        id: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> User:
        """Get a user by id.

        This endpoint is protected with rate limiting.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/users/{id}",
            "timeout": timeout,
        }

        return User(**self.client.request(**kwargs))
