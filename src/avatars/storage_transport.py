"""Which transport a client moves bytes through, and who decides it.

Three states, not two. ``True`` and ``False`` are a caller who has decided.
``None`` -- the default -- is a caller who has not, and then the deployment
decides: an operator who has checked that their storage endpoint is reachable
and correctly signed turns ``STORAGE_TRANSPORT`` to ``presigned`` on the server,
and every client new enough to ask follows, without anyone editing a notebook.

The question is asked once per client, on the first transfer and not at
construction. Building a client must not require a server to be reachable, and a
caller who never moves a file must not pay for a round trip.

Every way of failing to get an answer means credentials. A server too old to
serve ``/capabilities`` answers 404; a server too old to sign answers 404 to
``/access/presigned``; a server that is unreachable raises. Credentials is what
all of those callers had before this existed, so it is what they keep, and a
genuine connection problem shows up on the next request with its own error
instead of being reported here as a question about transports.

A caller who passed ``True`` has decided, so a 404 from the signing route is
their error and is raised. Quietly doing the opposite of what they asked would
hand S3 credentials to a process they had arranged would never hold one.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from structlog import get_logger

from avatars.base_client import ApiResponseError
from avatars.models import CapabilitiesResponse, StorageTransport

logger = get_logger(__name__)


class StorageTransportChoice:
    """The transport of one client, resolved at most once and then remembered."""

    def __init__(
        self,
        configured: bool | None = None,
        read_capabilities: Callable[[], CapabilitiesResponse] | None = None,
    ) -> None:
        """Hold the caller's choice, and the means of asking when they made none.

        Parameters
        ----------
        configured:
            ``True`` or ``False`` to force one transport, ``None`` to let the
            deployment choose.
        read_capabilities:
            How to ask the deployment. A client that cannot ask -- the
            in-process one, a test double -- leaves this out and uses
            credentials.

        """
        self._configured = configured
        self._read_capabilities = read_capabilities
        self._detected: bool | None = None

    def is_presigned(self) -> bool:
        """Whether the next transfer should go through a pre-signed URL."""
        if self._configured is not None:
            return self._configured
        if self._detected is None:
            self._detected = self._ask_the_deployment()
        return self._detected

    def _ask_the_deployment(self) -> bool:
        if self._read_capabilities is None:
            return False
        try:
            capabilities = self._read_capabilities()
        except Exception as error:  # noqa: BLE001 -- see the module docstring
            logger.debug(
                "could not read the capabilities of the server, using credentials",
                error=str(error),
            )
            return False
        return capabilities.storage_transport == StorageTransport.presigned

    def tolerates_a_missing_route(self, error: ApiResponseError) -> bool:
        """Whether a 404 from one route may be worked around with credentials.

        It may not for a caller who asked for pre-signed URLs: working around it
        means holding an S3 credential, which is what they arranged against.

        This records nothing: a route that is absent says what that one route
        can do and no more, so each caller decides for itself what its absence
        means for the rest of the session.
        """
        if self._configured is not None:
            return False
        return error.response.status_code == httpx.codes.NOT_FOUND

    def falls_back_on(self, error: ApiResponseError) -> bool:
        """Whether a failed *signing* request should be retried with credentials.

        ``True`` also records the answer, so the rest of the session asks this
        server for signatures no more. Only the signing route may say that: a
        server that signs is still a server that signs, whatever else it lacks.
        """
        if not self.tolerates_a_missing_route(error):
            return False

        logger.warning("this server does not sign storage URLs, using credentials")
        self._detected = False
        return True
