"""Who decides the transport, and what happens when the server cannot answer.

The cases that matter are the ones a deployment actually produces: a server old
enough to have no ``/capabilities``, a server that has it but does not sign, and
a caller who has decided for themselves and must not be quietly overruled.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest

from avatars.base_client import ApiResponseError
from avatars.data_upload import DataUploader
from avatars.file_downloader import FileDownloader
from avatars.models import CapabilitiesResponse, StorageTransport, StoredFile
from avatars.storage_transport import StorageTransportChoice
from tests.unit.conftest import FakeApiClient


def _capabilities(transport: StorageTransport | None) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        input_protocols=[],
        database_engines=[],
        connections=[],
        storage_transport=transport,
    )


def _answering(transport: StorageTransport | None) -> StorageTransportChoice:
    return StorageTransportChoice(None, lambda: _capabilities(transport))


def _not_found() -> ApiResponseError:
    return ApiResponseError("Error status 404 - Not Found", response=httpx.Response(404))


class TestWhoDecides:
    def test_the_deployment_is_asked_when_the_caller_said_nothing(self) -> None:
        assert _answering(StorageTransport.presigned).is_presigned()
        assert not _answering(StorageTransport.credentials).is_presigned()

    def test_a_server_too_old_to_answer_leaves_the_caller_on_credentials(self) -> None:
        """``/capabilities`` is newer than most deployments; its absence is normal."""

        def refuse() -> CapabilitiesResponse:
            raise _not_found()

        assert not StorageTransportChoice(None, refuse).is_presigned()

    def test_a_server_that_cannot_be_reached_leaves_the_caller_on_credentials(self) -> None:
        """The real error belongs to the transfer that follows, not to this question."""

        def refuse() -> CapabilitiesResponse:
            raise httpx.ConnectError("no route to host")

        assert not StorageTransportChoice(None, refuse).is_presigned()

    def test_a_server_that_omits_the_field_leaves_the_caller_on_credentials(self) -> None:
        assert not _answering(None).is_presigned()

    def test_the_question_is_asked_once(self) -> None:
        asked = 0

        def answer() -> CapabilitiesResponse:
            nonlocal asked
            asked += 1
            return _capabilities(StorageTransport.presigned)

        choice = StorageTransportChoice(None, answer)
        assert [choice.is_presigned() for _ in range(3)] == [True, True, True]
        assert asked == 1

    @pytest.mark.parametrize("decided", [True, False])
    def test_a_caller_who_decided_is_not_asked_about(self, decided: bool) -> None:
        asked = 0

        def explode() -> CapabilitiesResponse:
            # Counted as well as raised: `_ask_the_deployment` swallows every
            # exception, so for `decided=False` the raise alone would be caught
            # and the test would pass whether or not the server was asked.
            nonlocal asked
            asked += 1
            raise AssertionError("the server must not be asked")

        assert StorageTransportChoice(decided, explode).is_presigned() is decided
        assert asked == 0

    def test_a_client_with_no_server_to_ask_uses_credentials(self) -> None:
        """The in-process client and the test doubles have nothing to ask."""
        assert not StorageTransportChoice().is_presigned()


class TestFallingBack:
    def test_a_404_from_the_signing_route_sends_an_undecided_caller_back(self) -> None:
        choice = _answering(StorageTransport.presigned)
        assert choice.is_presigned()

        assert choice.falls_back_on(_not_found())
        assert not choice.is_presigned()

    def test_a_404_is_raised_at_a_caller_who_asked_for_pre_signed_urls(self) -> None:
        """Handing S3 credentials to a process told never to hold one is worse."""
        choice = StorageTransportChoice(True)

        assert not choice.falls_back_on(_not_found())
        assert choice.is_presigned()

    def test_any_other_refusal_is_the_caller_s_to_see(self) -> None:
        choice = _answering(StorageTransport.presigned)

        forbidden = ApiResponseError("Error status 403", response=httpx.Response(403))

        assert not choice.falls_back_on(forbidden)
        assert choice.is_presigned()


class TestThroughTheFileMovers:
    """The fallback has to work where it is needed: mid-transfer, not in the abstract."""

    def _client_on_a_server_that_does_not_sign(self) -> FakeApiClient:
        client = FakeApiClient(tables=["table1"])
        client.storage_transport = _answering(StorageTransport.presigned)

        def refuse(*_: object, **__: object) -> None:
            raise _not_found()

        client.results.get_presigned_url = refuse  # type: ignore[assignment,method-assign]
        client.results.get_presigned_urls_batch = refuse  # type: ignore[assignment,method-assign]
        return client

    def test_an_upload_completes_with_credentials(self, tmp_path: Path) -> None:
        client = self._client_on_a_server_that_does_not_sign()
        # The credentials transport writes through fsspec, so point it at a
        # local directory the way the other DataUploader tests do.
        client.results._upload_url_base = tmp_path.as_uri() + "/uploads"  # type: ignore[attr-defined]
        uploader = DataUploader(client, storage_endpoint_url=tmp_path.as_uri())

        uploader.upload_file_descriptor(io.BytesIO(b"col1\n1\n"), "dataset.csv")

        assert (tmp_path / "uploads" / "dataset.csv").read_bytes() == b"col1\n1\n"
        assert not client.storage_transport.is_presigned()

    def test_a_listing_goes_through_the_api_when_the_transport_is_pre_signed(self) -> None:
        """A client with no S3 credential has to be told what it uploaded."""
        client = FakeApiClient(tables=["table1"])
        client.storage_transport = _answering(StorageTransport.presigned)
        asked = False

        def listed(**_: object) -> list[StoredFile]:
            nonlocal asked
            asked = True
            return [StoredFile(name="patients.csv", size=9)]

        client.results.get_input_files = listed  # type: ignore[method-assign]

        files = DataUploader(
            client, storage_endpoint_url="http://unreachable.invalid"
        ).list_input_files()

        assert asked
        assert list(files) == ["patients.csv"]

    def test_a_listing_falls_back_to_credentials_on_a_server_without_the_route(
        self, tmp_path: Path
    ) -> None:
        """A server may sign and still be too old to list."""
        client = FakeApiClient(tables=["table1"])
        client.storage_transport = _answering(StorageTransport.presigned)
        client.results._upload_url_base = tmp_path.as_uri() + "/uploads"  # type: ignore[attr-defined]

        def refuse(**_: object) -> list[StoredFile]:
            raise _not_found()

        client.results.get_input_files = refuse  # type: ignore[method-assign]
        (tmp_path / "uploads").mkdir()
        (tmp_path / "uploads" / "patients.csv").write_bytes(b"a,b\n")

        files = DataUploader(client, storage_endpoint_url=tmp_path.as_uri()).list_input_files()

        assert list(files) == ["patients.csv"]
        # And the transfers that follow still ask for signatures: one missing
        # route is not the server saying it cannot sign.
        assert client.storage_transport.is_presigned()

    def test_a_listing_raises_at_a_caller_who_asked_for_pre_signed_urls(self) -> None:
        """Listing the storage needs the S3 credential they arranged against."""
        client = FakeApiClient(tables=["table1"])
        client.storage_transport = StorageTransportChoice(True)

        def refuse(**_: object) -> list[StoredFile]:
            raise _not_found()

        client.results.get_input_files = refuse  # type: ignore[method-assign]
        uploader = DataUploader(client, storage_endpoint_url="http://unreachable.invalid")

        with pytest.raises(ApiResponseError):
            uploader.list_input_files()

    def test_a_download_completes_with_credentials(self) -> None:
        client = self._client_on_a_server_that_does_not_sign()

        downloaded = FileDownloader(client).download_file("fakeurl/table1.privacy.json")

        assert downloaded is not None
        assert not client.storage_transport.is_presigned()
