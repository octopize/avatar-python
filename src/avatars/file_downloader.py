import io
import json
from typing import Any

import pandas as pd
import structlog
from IPython.display import HTML

from avatars import presigned_transfer
from avatars.base_client import ApiResponseError
from avatars.constants import TypeResults
from avatars.data_upload import decode_result
from avatars.models import FileAccess
from avatars.sdk_client import SdkClient
from avatars.storage import storage_url_of

logger = structlog.get_logger(__name__)


class FileDownloader:
    def __init__(self, api_client: SdkClient):
        self.client = api_client

    def _download_with_credentials(self, file_access: FileAccess) -> str | bytes:
        """Download a file using credentials."""
        return self.client.download_file(file_access=file_access)

    def _download_file_to_str(self, url: str) -> str | bytes:
        """Fetch one file, through whichever transport this client uses."""
        transport = self.client.storage_transport
        if transport.is_presigned():
            try:
                return self._download_presigned(url)
            except ApiResponseError as error:
                if not transport.falls_back_on(error):
                    raise

        file_access = self.client.results.get_permission_to_download(url)
        return self._download_with_credentials(file_access)

    def _download_presigned(self, url: str) -> str | bytes:
        """Ask the API to sign a read of one file, then fetch the signed URL.

        ``url`` may be a bare storage URL or the ``/access?url=`` envelope
        ``/results`` hands out; the API unwraps it either way.
        """
        grant = self.client.results.get_presigned_url(url=url)
        content = presigned_transfer.download(
            grant.presigned_url, should_verify_ssl=self.client.should_verify_ssl
        )
        return decode_result(grant.url, content)

    def _str_to_json(self, str_data: str) -> list[dict[str, Any]]:
        if not str_data.strip().startswith("["):
            str_data = f"[{str_data}]"
        parsed: list[dict[str, Any]] = json.loads(str_data)
        return parsed

    def _str_to_csv(self, str_data: str) -> pd.DataFrame:
        return pd.read_csv(io.StringIO(str_data))

    def _bytes_to_parquet(self, bytes_data: bytes) -> pd.DataFrame:
        return pd.read_parquet(io.BytesIO(bytes_data))

    def _str_to_html(self, str_data: str) -> HTML:
        # IPython.display.HTML ships py.typed but its __init__ is unannotated.
        return HTML(str_data)  # type: ignore[no-untyped-call]

    def _str_to_file(self, str_data: bytes, path: str) -> None:
        with open(path, "wb") as fd:
            fd.write(str_data)

    def _str_to_results(
        self, str_data: str | bytes, extension: str, path: str | None = None
    ) -> TypeResults:
        data: TypeResults = None
        match extension:
            case ".json":
                if isinstance(str_data, str):
                    data = self._str_to_json(str_data)
            case ".csv":
                if isinstance(str_data, str):
                    data = self._str_to_csv(str_data)
            case ".parquet":
                if isinstance(str_data, bytes):
                    data = self._bytes_to_parquet(str_data)
            case ".pdf" | ".docx":
                if path is None:
                    raise ValueError("Expected path to save the PDF file")
                if isinstance(str_data, bytes):
                    self._str_to_file(str_data, path)
                    data = f"Report saved successfully {path}"
            case ".md":
                if path is not None:
                    content = str_data if isinstance(str_data, bytes) else str_data.encode()
                    self._str_to_file(content, path)
                    data = f"Report saved successfully {path}"
            case ".html":
                if isinstance(str_data, str):
                    data = self._str_to_html(str_data)
        return data

    def download_file(self, url: str, path: str | None = None) -> TypeResults:
        """Download a file from the given URL and return its content in an appropriate format.
        If path is provided, save the file to that path.
        """
        str_data = self._download_file_to_str(url)
        extension = url.rsplit(".", maxsplit=1)[-1]
        return self._str_to_results(str_data, f".{extension}", path)

    def download_files_batch(self, urls: list[str]) -> dict[str, TypeResults]:
        """Download several files at once, keyed by the URL the caller passed in.

        A URL the API declined to hand back is absent from the result rather than
        raising, so one stale result does not cost a caller the rest of the job.
        """
        if not urls:
            return {}

        return {
            url: self._str_to_results(data, f".{url.rsplit('.', maxsplit=1)[-1]}")
            for url, data in self._fetch_batch(urls).items()
        }

    def _fetch_batch(self, urls: list[str]) -> dict[str, str | bytes]:
        """Fetch each URL's bytes, through whichever transport is configured.

        The only thing that differs between the two transports; how bytes become
        a DataFrame is decided once, by the caller.
        """
        fetched = self._fetch_batch_through_transport(urls)

        if missing := [url for url in urls if url not in fetched]:
            # Either the API declined to sign them, or they came back under a
            # name this client did not ask for. The second is a bug and would
            # otherwise be indistinguishable from the first.
            logger.warning(
                "some files were not returned by the API and have been skipped",
                count=len(missing),
                urls=missing,
            )
        return fetched

    def _fetch_batch_through_transport(self, urls: list[str]) -> dict[str, str | bytes]:
        """Fetch a batch, retrying with credentials if the server cannot sign."""
        transport = self.client.storage_transport
        if transport.is_presigned():
            try:
                return self._fetch_batch_presigned(urls)
            except ApiResponseError as error:
                if not transport.falls_back_on(error):
                    raise

        return self._fetch_batch_with_credentials(urls)

    def _fetch_batch_presigned(self, urls: list[str]) -> dict[str, str | bytes]:
        grants = {grant.url: grant for grant in self.client.results.get_presigned_urls_batch(urls)}
        fetched: dict[str, str | bytes] = {}
        for url in urls:
            grant = grants.get(url) or grants.get(storage_url_of(url))
            if grant is None:
                continue
            content = presigned_transfer.download(
                grant.presigned_url, should_verify_ssl=self.client.should_verify_ssl
            )
            fetched[url] = decode_result(grant.url, content)
        return fetched

    def _fetch_batch_with_credentials(self, urls: list[str]) -> dict[str, str | bytes]:
        accesses = {
            access.url: access
            for access in self.client.results.get_permissions_to_download_batch(urls)
        }
        return {
            url: self._download_with_credentials(accesses[url]) for url in urls if url in accesses
        }
