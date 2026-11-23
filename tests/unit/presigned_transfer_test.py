"""The pre-signed transport, against a real HTTP server that checks the URL.

A fake that accepted anything would not catch the mistakes that matter here —
dropping the query string, probing with HEAD before reading, or appending a path
segment to the signed URL — because all three still produce a plausible request.
So these run against a throwaway ``http.server`` that behaves the way storage
does: it serves only the exact path it was given, only for the method that was
"signed", and only while the query string is intact.
"""

from __future__ import annotations

import gzip
import io
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

import fsspec
import pandas as pd
import pytest

from avatars.data_upload import DataUploader, decode_result
from avatars.file_downloader import FileDownloader
from avatars.presigned_transfer import PresignedTransferError, download, upload
from avatars.storage_transport import StorageTransportChoice
from tests.unit.conftest import FakeApiClient

# What the fake server treats as the signature: present and matching the method.
_SIGNATURE_PARAM = "X-Amz-Signature"
_METHOD_PARAM = "X-Amz-Method"


class _StorageHandler(BaseHTTPRequestHandler):
    """A stand-in for object storage that honours the grant in the URL."""

    # Shared on purpose: http.server builds a new handler per request, so the
    # stored objects have to outlive the instance that wrote them.
    objects: ClassVar[dict[str, bytes]] = {}
    # Paths this server answers with `Content-Encoding: gzip`, as storage does
    # for an object uploaded with that header.
    encoded: ClassVar[set[str]] = set()

    def log_message(self, *args: object) -> None:  # keep the test output quiet
        return

    def _grant(self) -> tuple[str, str | None, str | None]:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        return (
            parsed.path,
            next(iter(query.get(_SIGNATURE_PARAM, [])), None),
            next(iter(query.get(_METHOD_PARAM, [])), None),
        )

    def _refuse(self) -> None:
        self.send_response(403)
        body = b"<Error><Code>SignatureDoesNotMatch</Code></Error>"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self) -> None:
        path, signature, method = self._grant()
        if not signature or method != "PUT":
            self._refuse()
            return

        length = int(self.headers.get("Content-Length", 0))
        type(self).objects[path] = self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path, signature, method = self._grant()
        if not signature or method != "GET" or path not in type(self).objects:
            self._refuse()
            return

        body = type(self).objects[path]
        self.send_response(200)
        if path in type(self).encoded:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        """Storage refuses a HEAD against a URL signed for GET."""
        self._refuse()


class _RedirectingHandler(BaseHTTPRequestHandler):
    """Storage behind an address that redirects, which a signed URL cannot follow."""

    def log_message(self, *args: object) -> None:
        return

    def _redirect(self) -> None:
        self.send_response(301)
        self.send_header("Location", "https://elsewhere.invalid" + self.path)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PUT(self) -> None:
        self._redirect()

    def do_GET(self) -> None:
        self._redirect()


@pytest.fixture
def storage() -> Iterator[str]:
    _StorageHandler.objects = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StorageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def redirecting_storage() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _grant_url(storage: str, key: str, method: str) -> str:
    return f"{storage}/{key}?{_SIGNATURE_PARAM}=abc123&{_METHOD_PARAM}={method}"


def _client_pointed_at(storage: str) -> FakeApiClient:
    """A fake API whose grants point at the throwaway storage server."""
    client = FakeApiClient(
        sign=lambda url, method: _grant_url(storage, url.removeprefix("s3://"), method)
    )
    client.storage_transport = StorageTransportChoice(configured=True)
    return client


def test_a_round_trip_moves_the_bytes_unchanged(storage: str) -> None:
    content = b"col1,col2\n1,2\n"

    upload(_grant_url(storage, "bucket/input/dataset.csv", "PUT"), content)

    assert download(_grant_url(storage, "bucket/input/dataset.csv", "GET")) == content


def test_a_large_body_survives_streaming(storage: str) -> None:
    """The download streams in chunks; it must reassemble exactly."""
    content = bytes(range(256)) * 40_000  # ~10 MiB, several chunks

    upload(_grant_url(storage, "bucket/input/big.bin", "PUT"), content)

    assert download(_grant_url(storage, "bucket/input/big.bin", "GET")) == content


def test_a_stream_is_uploaded_from_where_it_is_positioned(storage: str) -> None:
    """``upload`` takes ``bytes | BinaryIO``, so a stream has to work as well.

    A signed PUT needs Content-Length, and httpx reads that length from the size
    of a stream rather than from what remains in it. A stream already positioned
    past its start announced more than it sent, and the transfer failed on a
    length nobody could satisfy.
    """
    stream = io.BytesIO(b"headerXcol1,col2\n1,2\n")
    stream.seek(len(b"headerX"))

    upload(_grant_url(storage, "bucket/input/positioned.csv", "PUT"), stream)

    assert _StorageHandler.objects["/bucket/input/positioned.csv"] == b"col1,col2\n1,2\n"


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"a\r\nb\r\nc", id="crlf"),
        pytest.param(b"a\rb\rc", id="cr"),
        pytest.param(b"a\nb\nc", id="lf"),
        pytest.param("é\r\nz".encode(), id="non-ascii-with-crlf"),
    ],
)
def test_a_text_result_reads_the_same_whichever_transport_fetched_it(
    raw: bytes, tmp_path: Path
) -> None:
    r"""The transport is meant to be invisible to the caller, newlines included.

    The credentialed path reads text through ``fsspec``'s ``read_text``, which
    wraps the file with ``newline=None`` and so turns ``\r\n`` and ``\r`` into
    ``\n``. This compares against that implementation rather than against an
    assumption about it, so the day fsspec changes, this says so.
    """
    stored = tmp_path / "result.csv"
    stored.write_bytes(raw)
    credentialed = fsspec.filesystem("file").read_text(str(stored), encoding="utf-8")

    assert decode_result("s3://bucket/result.csv", raw) == credentialed


def test_a_binary_result_is_never_newline_translated() -> None:
    r"""A parquet file holding \r\n is data, not a line ending."""
    raw = b"PAR1\r\n\x00\r"

    assert decode_result("s3://bucket/result.parquet", raw) == raw


def test_the_query_string_is_sent_untouched(storage: str) -> None:
    """Dropping it is the easy mistake, and it fails closed rather than loudly."""
    upload(_grant_url(storage, "bucket/input/dataset.csv", "PUT"), b"x")

    with pytest.raises(PresignedTransferError) as refused:
        download(f"{storage}/bucket/input/dataset.csv")

    assert refused.value.status_code == 403


def test_a_refusal_says_what_to_do_about_it(storage: str) -> None:
    """A grant that has expired is the common case; the message has to name it."""
    with pytest.raises(PresignedTransferError, match="expired"):
        download(_grant_url(storage, "bucket/missing.csv", "GET"))


def test_the_uploader_sends_no_s3_credential_when_presigning(storage: str) -> None:
    """End-to-end through DataUploader, with the API replaced by a stub.

    What this pins down is the call shape: the uploader asks for a ``put`` grant
    and PUTs to whatever URL it is handed, rather than reaching for the storage
    endpoint and a key of its own.
    """
    api_client = _client_pointed_at(storage)

    uploader = DataUploader(api_client, storage_endpoint_url="http://unused.invalid")
    uploader.upload_file_descriptor(io.BytesIO(b"a,b\n1,2\n"), "dataset.csv")

    assert _StorageHandler.objects["/test-bucket/uploads/dataset.csv"] == b"a,b\n1,2\n"


def test_the_downloader_reads_back_what_the_uploader_wrote(storage: str) -> None:
    """Upload and download are the two halves of the same round trip."""
    api_client = _client_pointed_at(storage)

    DataUploader(api_client, storage_endpoint_url="http://unused.invalid").upload_file_descriptor(
        io.BytesIO(b"col1,col2\n1,2\n"), "dataset.csv"
    )

    downloaded = FileDownloader(api_client).download_file("s3://test-bucket/uploads/dataset.csv")

    assert isinstance(downloaded, pd.DataFrame)
    assert downloaded.to_dict("records") == [{"col1": 1, "col2": 2}]


def test_a_batch_download_returns_what_the_api_signed_and_skips_what_it_did_not(
    storage: str,
) -> None:
    """The API drops files the caller does not own; the batch must not raise.

    Keyed by the URL the caller passed in, so a caller can line the results up
    with its own request without knowing how the API spells the storage URL.
    """
    api_client = _client_pointed_at(storage)

    uploader = DataUploader(api_client, storage_endpoint_url="http://unused.invalid")
    uploader.upload_file_descriptor(io.BytesIO(b"col1\n1\n"), "mine.csv")

    mine = "s3://test-bucket/uploads/mine.csv"
    theirs = "s3://other-tenant/uploads/theirs.csv"

    # The API signs only what the caller owns — the same shape as a 403 skip.
    only_mine = api_client.results.get_presigned_url(mine)
    api_client.results.get_presigned_urls_batch = lambda urls, **_: [only_mine]  # type: ignore[method-assign]

    results = FileDownloader(api_client).download_files_batch([mine, theirs])

    assert list(results) == [mine]
    assert isinstance(results[mine], pd.DataFrame)


def test_a_batch_download_of_nothing_asks_the_api_nothing(storage: str) -> None:
    api_client = _client_pointed_at(storage)

    def explode(urls: list[str], **_: object) -> list[object]:
        raise AssertionError("the API should not be called for an empty batch")

    api_client.results.get_presigned_urls_batch = explode  # type: ignore[assignment,method-assign]

    assert FileDownloader(api_client).download_files_batch([]) == {}


def test_an_upload_that_is_redirected_is_not_reported_as_stored(
    redirecting_storage: str,
) -> None:
    """A deployment whose storage address redirects would otherwise lose data silently.

    httpx does not follow redirects, and a signature covers the host, so it
    could not survive one anyway. The bytes did not move, so this has to raise
    rather than return.
    """
    with pytest.raises(PresignedTransferError) as refused:
        upload(_grant_url(redirecting_storage, "bucket/input/dataset.csv", "PUT"), b"a,b\n1,2\n")

    assert refused.value.status_code == 301


def test_a_download_that_is_redirected_does_not_return_the_redirect_body(
    redirecting_storage: str,
) -> None:
    with pytest.raises(PresignedTransferError) as refused:
        download(_grant_url(redirecting_storage, "bucket/input/dataset.csv", "GET"))

    assert refused.value.status_code == 301


def test_a_content_encoded_object_comes_back_as_it_is_stored(storage: str) -> None:
    """The bytes in the bucket, not the bytes a decoder makes of them.

    Storage returns an object stored with `Content-Encoding: gzip` under that
    header. Decoding it here would hand the caller something that is neither
    what was uploaded nor what the credentialed path returns, and a parquet
    file would arrive as something pandas cannot read.
    """
    stored = gzip.compress(b"col1,col2\n1,2\n" * 50)
    _StorageHandler.objects["/bucket/input/encoded.csv.gz"] = stored
    _StorageHandler.encoded.add("/bucket/input/encoded.csv.gz")

    try:
        assert download(_grant_url(storage, "bucket/input/encoded.csv.gz", "GET")) == stored
    finally:
        _StorageHandler.encoded.clear()
