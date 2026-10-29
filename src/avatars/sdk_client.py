"""The client surface the hand-written SDK actually uses.

This file is **not** generated. It exists so that :class:`avatars.runner.Runner`,
:class:`avatars.manager.Manager` and their collaborators can be handed either the
generated :class:`avatars.client.ApiClient` (which talks HTTP to an Avatar server)
or :class:`avatars.serverless.client.ServerlessClient` (which runs the engine
in-process), without either of them knowing which one it has.

Why a Protocol rather than a base class: ``ApiClient`` is generated from
``services/api/schema.json`` and must never be edited, so it cannot be made to
inherit from anything here. Structural typing is the only way to state "these two
unrelated classes are interchangeable *for the SDK's purposes*".

Why only these members: the protocol deliberately describes the **subset** the SDK
calls, not the whole generated surface. A serverless client has no API keys, no
event logs and no OpenAPI document, and pretending otherwise would oblige it to
implement forty methods that cannot mean anything without a server.

What is deliberately absent
---------------------------
The generated methods all take a keyword-only ``timeout``. It is not declared here
because the SDK never passes it -- and requiring it would oblige an in-process
client to accept a parameter that cannot mean anything without a socket. A protocol
member may be satisfied by a method with extra *optional* parameters, so the
generated client still fits.

Keeping it honest
-----------------
``_generated_client_satisfies_protocol`` below is a compile-time assertion: if a
schema regeneration changes the signature of a method the SDK depends on, mypy
fails *here*, naming the method, rather than at some call site months later.
Regeneration touches ``services/client/src/**``, which runs ``just typecheck`` in
``avatar-python-lci.yml``, so the gate cannot be skipped.
``tests/unit/serverless/parity_test.py`` backs it at runtime.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import pandas as pd

from avatars.input_files import InputFiles
from avatars.models import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    CompatibilityResponse,
    FileAccess,
    JobKind,
    JobResponse,
    JobResponseList,
    MeUser,
    ResourceSetResponse,
)

if TYPE_CHECKING:
    from avatars.client import ApiClient


@runtime_checkable
class ResourcesApi(Protocol):
    """The ``/resources`` endpoints the SDK uses."""

    def put_resources(self, display_name: str, yaml_string: str) -> ResourceSetResponse: ...

    def get_resources(self, set_name: str) -> Any: ...


@runtime_checkable
class JobsApi(Protocol):
    """The ``/jobs`` endpoints the SDK uses."""

    def get_jobs(
        self,
        kind: list[JobKind] | None = ...,
        display_name: str | None = ...,
        set_name: str | None = ...,
        names: list[str] | None = ...,
        limit: int | None = ...,
        include_deleted: bool | None = ...,
    ) -> JobResponseList: ...

    def get_last_jobs(self) -> JobResponseList: ...

    def get_job_status(self, job_name: str) -> JobResponse: ...

    def cancel_job(self, job_name: str) -> JobResponse: ...

    def bulk_delete_jobs(self, request: BulkDeleteRequest) -> BulkDeleteResponse: ...


@runtime_checkable
class ResultsApi(Protocol):
    """The ``/results``, ``/access`` and ``/upload_url`` endpoints the SDK uses."""

    def get_results(self, job_name: str) -> Any: ...

    def get_permission_to_download(self, url: str) -> FileAccess: ...

    def get_permissions_to_download_batch(self, urls: list[str]) -> list[FileAccess]: ...

    def get_upload_url(self) -> Any: ...


@runtime_checkable
class UsersApi(Protocol):
    """The ``/users`` endpoints the SDK uses."""

    def get_me(self) -> MeUser: ...


@runtime_checkable
class HealthApi(Protocol):
    """The ``/health`` endpoint the SDK uses."""

    def get_health(self) -> Any: ...


@runtime_checkable
class CompatibilityApi(Protocol):
    """The ``/check_client`` endpoint the SDK uses."""

    def is_client_compatible(self) -> CompatibilityResponse: ...


@runtime_checkable
class UploadFile(Protocol):
    """``client.upload_file``, which callers invoke by keyword."""

    def __call__(self, data: "str | pd.DataFrame", key: str) -> None: ...


@runtime_checkable
class DownloadFile(Protocol):
    """``client.download_file``, which callers invoke by keyword."""

    def __call__(self, file_access: FileAccess) -> str | bytes: ...


@runtime_checkable
class ListInputFiles(Protocol):
    """``client.list_input_files``: the files of the input directory, newest first."""

    def __call__(self) -> InputFiles: ...


@runtime_checkable
class SdkClient(Protocol):
    """What ``Runner``, ``Manager`` and their collaborators require of a client.

    The sub-APIs are declared as read-only properties rather than plain attributes
    so they are covariant: a mutable protocol attribute demands an *exact* type
    match, which would reject ``ApiClient.jobs`` (a generated ``Jobs``) for being a
    mere implementation of ``JobsApi`` rather than that class itself. An
    implementation is free to satisfy them with ordinary instance attributes.

    ``upload_file``/``download_file``/``list_input_files`` are read-only too, and
    spelled as call protocols rather than ``Callable[...]`` because callers pass
    their arguments by keyword. Read-only matters here: on ``ApiClient`` they are
    instance attributes bound from the ``DataUploader``, while on a test double or
    the serverless client they are ordinary methods, and only a read-only member
    accepts both.
    """

    base_url: str
    should_verify_ssl: bool

    @property
    def upload_file(self) -> UploadFile: ...

    @property
    def download_file(self) -> DownloadFile: ...

    @property
    def list_input_files(self) -> ListInputFiles: ...

    @property
    def resources(self) -> ResourcesApi: ...

    @property
    def jobs(self) -> JobsApi: ...

    @property
    def results(self) -> ResultsApi: ...

    @property
    def users(self) -> UsersApi: ...

    @property
    def health(self) -> HealthApi: ...

    @property
    def compatibility(self) -> CompatibilityApi: ...

    def is_using_api_key(self) -> bool: ...

    def send_request(self, *, method: str, url: str, **kwargs: Any) -> Any: ...


def _generated_client_satisfies_protocol(client: "ApiClient") -> SdkClient:
    """Compile-time proof that the generated client still fits.

    Never called. If a regeneration of ``api.py``/``client.py`` drops or reshapes
    something the SDK depends on, mypy fails on this return statement and names the
    offending member -- which is the whole point of the file.
    """
    return client
