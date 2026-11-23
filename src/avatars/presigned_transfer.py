"""Moving bytes with a pre-signed URL, and nothing else.

The credentialed path in :mod:`avatars.data_upload` needs three things from the
deployment before it can transfer a byte: the S3 endpoint, an access key and a
secret. A pre-signed URL carries all three in the query string, already spent on
one object, one method and one expiry. So this module is deliberately thin —
``httpx`` against a URL the API produced — and has no S3 client, no fsspec
filesystem and no storage configuration of its own.

Two details are worth stating because they are not obvious:

* **Do not probe before transferring.** A signature covers the HTTP method, so
  the ``HEAD`` that an S3 filesystem issues to size a file before reading it is
  refused by a URL signed for ``GET``. Stream the ``GET`` instead.
* **Do not edit the URL.** Appending a path segment, changing the key or
  stretching ``X-Amz-Expires`` all invalidate the signature. Ask the API for a
  new grant instead.
* **Only 2xx is a transfer.** Redirects are not followed, because a signature
  covers the host and would not survive one. A 3xx therefore means the bytes
  did not move, and is refused like any other failure: treating it as success
  would let a deployment whose storage address redirects report every upload
  as stored while nothing was written.
"""

from __future__ import annotations

import io
from typing import BinaryIO

import httpx
import structlog

logger = structlog.get_logger(__name__)

# A pre-signed transfer is one request that may carry a whole dataset, so it
# needs a budget unrelated to the one for API calls.
DEFAULT_TRANSFER_TIMEOUT_SECONDS = 600

_CHUNK_SIZE = 1024 * 1024


class PresignedTransferError(Exception):
    """A transfer against a pre-signed URL was refused by the storage."""

    def __init__(self, method: str, status_code: int, body: str) -> None:
        self.status_code = status_code
        super().__init__(
            f"Storage did not complete the pre-signed {method}: HTTP {status_code}. "
            "A 3xx means the storage address redirects, which a signed URL cannot "
            "survive; otherwise the grant may have expired — ask the API for a new one. "
            f"Response: {body[:500]}"
        )


def upload(
    presigned_url: str,
    content: bytes | BinaryIO,
    *,
    should_verify_ssl: bool = True,
    timeout: int = DEFAULT_TRANSFER_TIMEOUT_SECONDS,
) -> None:
    """PUT ``content`` at a URL the API signed for exactly this object."""
    # A signed PUT carries Content-Length, so the body cannot be chunked, and
    # httpx takes that length from the size of a stream rather than from what is
    # left to read in it. A stream positioned past its start therefore announces
    # more than it sends, and the transfer fails on a length nobody can satisfy.
    # Reading it here costs no more memory than the one caller already spends,
    # since it hands over the result of its own ``read``.
    body = content if isinstance(content, bytes) else content.read()

    with httpx.Client(verify=should_verify_ssl, timeout=timeout) as client:
        response = client.put(presigned_url, content=body)

    if not response.is_success:
        raise PresignedTransferError("PUT", response.status_code, response.text)

    logger.debug("uploaded through a pre-signed url", status_code=response.status_code)


def download(
    presigned_url: str,
    *,
    should_verify_ssl: bool = True,
    timeout: int = DEFAULT_TRANSFER_TIMEOUT_SECONDS,
) -> bytes:
    """GET the object a URL was signed for, streaming it into memory.

    Streamed rather than read whole so a large result does not have to exist
    twice: once in httpx's buffer and once in the returned value.

    Raw, not decoded. An object stored with ``Content-Encoding: gzip`` is
    returned with that header, and ``iter_bytes`` would decompress it: the
    caller would get bytes that are not the ones in the bucket, and not the
    ones the credentialed path returns either, since an S3 filesystem hands
    back what is stored. A parquet file would arrive as something pandas
    cannot read, blaming the file rather than the transport.
    """
    with httpx.Client(verify=should_verify_ssl, timeout=timeout) as client:
        with client.stream("GET", presigned_url) as response:
            if not response.is_success:
                response.read()
                raise PresignedTransferError("GET", response.status_code, response.text)

            # Written into a buffer rather than joined: ``b"".join`` keeps every
            # chunk alive until the last one arrives and then allocates the
            # result beside them, which is the second copy this docstring
            # promises not to make.
            buffer = io.BytesIO()
            for chunk in response.iter_raw(_CHUNK_SIZE):
                buffer.write(chunk)
            content = buffer.getvalue()
    logger.debug("downloaded through a pre-signed url", size=len(content))
    return content
