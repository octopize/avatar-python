# This file has been generated - DO NOT MODIFY
# API Version : 3.20.2


import logging
from typing import TYPE_CHECKING, Any, TypeVar

from avatars.models import (
    ApiKey,
    BulkDeleteRequest,
    BulkDeleteResponse,
    CapabilitiesResponse,
    CompatibilityResponse,
    ConnectionDraft,
    ConnectionList,
    ConnectionPatch,
    ConnectionPresetList,
    ConnectionPresetRequest,
    ConnectionProbe,
    ConnectionSample,
    ConnectionSampleRequest,
    ConnectionSummary,
    CreateApiKeyRequest,
    CreditsInfo,
    EngineList,
    EventLogResponse,
    FeaturesInfo,
    FileAccess,
    JobCreateRequest,
    JobCreateResponse,
    JobFlowCreateRequest,
    JobFlowCreateResponse,
    JobKind,
    JobResponse,
    JobResponseList,
    MeUser,
    ObjectType,
    ResourceSetResponse,
    User,
    Verb,
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


class Capabilities:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def get_capabilities(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> CapabilitiesResponse:
        """What this deployment can do, and which connections the caller can use.

        Cheap and cacheable per caller: it reads process-local registries and
        settings, plus the caller's organization's connections, and changes when
        somebody changes one of those rather than while a form is filled in.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/capabilities",  # noqa: F541
            "timeout": timeout,
        }

        return CapabilitiesResponse(**self.client.request(**kwargs))


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


class Connections:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def list_connections(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionList:
        """The connections the caller can use: the deployment's, then their organization's.

        The same list `capabilities` reports. `{"connections": [...]}` rather than a
        bare list, which is the shape the web client reads -- it rendered the bare
        list as an empty picker.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/connections",  # noqa: F541
            "timeout": timeout,
        }

        return ConnectionList(**self.client.request(**kwargs))

    def list_engines(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> EngineList:
        """The kinds of database a connection can be made to, and the form for each.

        The web form is generated from this: which fields an engine takes, which of
        them are secret, their defaults, and whether the kind is `sql` or
        `documents`. A kind with `available: false` is described so it can be shown,
        and cannot be stored yet. Adding an engine is a change here, not in a client.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/connections/engines",  # noqa: F541
            "timeout": timeout,
        }

        return EngineList(**self.client.request(**kwargs))

    def list_connection_presets(
        self,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionPresetList:
        """The demo and sample connections this deployment offers to add.

        Offered, not listed: none of them is in anybody's connections until they add
        it with `POST /connections/presets`. Empty on a deployment that ships none.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/connections/presets",  # noqa: F541
            "timeout": timeout,
        }

        return ConnectionPresetList(**self.client.request(**kwargs))

    def add_connection_presets(
        self,
        request: ConnectionPresetRequest,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Add every connection of one kind this deployment offers: `demo` or `sample`.

        To the caller's own connections by default (`scope: user`); `organization`
        adds them for every member, and is an admin's call. Answers with the ones it
        added: a name the caller can already use is left as it is, so adding twice
        adds nothing the second time. 404 when the deployment offers none of that kind.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/connections/presets",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return self.client.request(**kwargs)

    def put_connection(
        self,
        request: ConnectionDraft,
        name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionSummary:
        """Store, or replace whole, the connection *name*.

        With the default `organization` scope it is for every member of the caller's
        organization, and admins only. With `user` it is the caller's own: any member
        may store one, and nobody else can see or use it.

        201 when it is new, 200 when it replaced one. The DSN is checked -- it must
        parse, and its scheme must be the declared engine -- encrypted, and never
        returned: the answer carries its display form. A name the deployment
        already uses is refused with 409, and 503 means this deployment has no
        encryption key and cannot store connections at all.
        """
        kwargs: dict[str, Any] = {
            "method": "put",
            "url": f"/connections/{name}",
            "timeout": timeout,
            "json_data": request,
        }

        return ConnectionSummary(**self.client.request(**kwargs))

    def patch_connection(
        self,
        request: ConnectionPatch,
        name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionSummary:
        """Rename or relabel the connection *name* without re-entering its credentials.

        Who may: an admin for the organization's, its owner for their own. 404 for a
        connection the caller cannot see, 409 for one of the deployment's, 422 for a name that
        is invalid or taken.
        """
        kwargs: dict[str, Any] = {
            "method": "patch",
            "url": f"/connections/{name}",
            "timeout": timeout,
            "json_data": request,
        }

        return ConnectionSummary(**self.client.request(**kwargs))

    def delete_connection(
        self,
        name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> Any:
        """Forget the connection *name*: an admin for the organization's, its owner for their own.

        Nothing that used it is touched: a job already submitted carries what it
        needs. 404 when the organization has none by that name. One the deployment declares
        cannot be removed from its configuration here; an admin takes it out of use for their
        own organization instead (it is no longer listed or resolved for them, and nobody else is
        affected), and a member who is not an admin is refused with 403.
        """
        kwargs: dict[str, Any] = {
            "method": "delete",
            "url": f"/connections/{name}",
            "timeout": timeout,
        }

        return self.client.request(**kwargs)

    def test_draft_connection(
        self,
        request: ConnectionDraft,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionProbe:
        """Open a connection that is not stored yet, and report what is there.

        Held to the rules of storing it: admins for the organization's scope, any
        member for their own.

        So a mistyped host is found while the form is still open, rather than by
        saving a credential nothing can use. The same probe as
        `/connections/{name}/test`, under the same rules as storing it.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/connections/test",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return ConnectionProbe(**self.client.request(**kwargs))

    def test_connection(
        self,
        name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionProbe:
        """Open the connection called *name* and report what is there.

        Synchronous: it is seconds of I/O, and the answer is only useful while
        somebody is looking at the screen that asked for it. A job kind would cost a
        resource document, a queue and a poll for that.

        404 for a name the caller cannot use -- named rather than answered with
        `reachable: false`, because a connection that does not exist is a different
        problem from one that will not open. Every test is recorded in the event
        log, by name and outcome.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/connections/{name}/test",
            "timeout": timeout,
        }

        return ConnectionProbe(**self.client.request(**kwargs))

    def sample_connection(
        self,
        request: ConnectionSampleRequest,
        name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> ConnectionSample:
        """A few values of the named columns, so a join can be checked by eye.

        The subject editor puts the keys of each picked table side by side --
        ``person_id: 1001, 1002`` next to ``customer_ref: 1001, 1002`` -- because a
        subject declared on the wrong column does not fail: every person gets an
        identity of their own in each table, and the run succeeds.

        This returns **production values**, like `DatabaseProtocol.sample` and for
        the same reason: the person choosing the key has to see some, and is
        already entitled to the data. So it is minimised rather than refused --
        only the columns asked for, at most twenty values of each, never a whole
        row -- and every read is recorded in the event log, by connection, tables
        and row count. Never the values.

        Opened and failed exactly as `/test` is: 404 for a name the caller cannot
        use, a displayable `error` for one that will not open.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/connections/{name}/sample",
            "timeout": timeout,
            "json_data": request,
        }

        return ConnectionSample(**self.client.request(**kwargs))


class EventLogs:
    def __init__(self, client: "ApiClient") -> None:
        self.client = client

    def list_my_event_logs(
        self,
        verb: list[Verb] | None = None,
        object_type: list[ObjectType] | None = None,
        created_from: str | None = None,
        created_before: str | None = None,
        starting_after: str | None = None,
        limit: int | None = None,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> list[EventLogResponse]:
        """Return one page of the audit trail of the authenticated user, most recent first.

        The events are in the order of ``created_at`` desc, then ``id`` desc. A page holds
        at most ``limit`` events. To get the next page, send the same filters with
        ``starting_after`` set to the ``id`` of the last event of the page. A page with
        fewer than ``limit`` events is the last page.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/event-logs",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                verb=verb,
                object_type=object_type,
                created_from=created_from,
                created_before=created_before,
                starting_after=starting_after,
                limit=limit,
            ),
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
        names: list[str] | None = None,
        limit: int | None = None,
        include_deleted: bool | None = None,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobResponseList:
        """List the jobs of the current user, newest first.

        All filters apply together. With `names`, the response contains only the jobs of the
        current user that have one of these names. A name that matches no job is absent from
        the response, and the request does not fail. `limit` applies after the filters.
        A request with more than 100 distinct names returns status 400.
        """
        kwargs: dict[str, Any] = {
            "method": "get",
            "url": f"/jobs",  # noqa: F541
            "timeout": timeout,
            "params": dict(
                kind=kind,
                display_name=display_name,
                set_name=set_name,
                names=names,
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

    def create_job_flow(
        self,
        request: JobFlowCreateRequest,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobFlowCreateResponse:
        """Launch everything a set describes, as one request.

        The set is the declaration: each of its parameters documents is a job, and
        which documents exist already says what should run. So a caller says
        "launch this set" rather than naming the jobs, their order and what each
        waits for -- which every client otherwise has to know, and agree about.

        One request rather than one per job, because a flow is one intention. A
        caller that had three jobs created and the fourth refused held a half-built
        run with no way to say that none of it should have started; and creating
        them one at a time was enough requests to meet this API's own rate limit,
        since a database run launches one flow per group of related tables.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/flow",  # noqa: F541
            "timeout": timeout,
            "json_data": request,
        }

        return JobFlowCreateResponse(**self.client.request(**kwargs))

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
        """Delete a single job by name, cancelling it first if it is still running."""
        kwargs: dict[str, Any] = {
            "method": "delete",
            "url": f"/jobs/{job_name}",
            "timeout": timeout,
        }

        return JobResponse(**self.client.request(**kwargs))

    def cancel_job(
        self,
        job_name: str,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> JobResponse:
        """Stop a job: at once if it has not started, at its next safe point if it has.

        A job no worker has picked up comes back ``cancelled``. A running one comes
        back as it was, with its phase set to ``cancelling``, and turns ``cancelled``
        once it stops -- between stages, batches, tables or documents, never inside
        one. It can still finish if it was past its last such point.

        A database copy stopped while writing leaves the tables it had finished in
        the target: writes cannot be rolled back across tables. The job's
        ``exception`` names them.

        The jobs waiting on it are cancelled too. 409 for a job that is already over.
        """
        kwargs: dict[str, Any] = {
            "method": "post",
            "url": f"/jobs/{job_name}/cancel",
            "timeout": timeout,
        }

        return JobResponse(**self.client.request(**kwargs))

    def bulk_delete_jobs(
        self,
        request: BulkDeleteRequest,
        *,
        timeout: int | None = DEFAULT_TIMEOUT,
    ) -> BulkDeleteResponse:
        """Delete multiple jobs in a single request. Maximum 100 jobs at once.

        A job that is still running is cancelled before it is deleted.
        """
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
