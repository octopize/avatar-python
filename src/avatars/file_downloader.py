import io
import json
from typing import Any

import pandas as pd
from IPython.display import HTML

from avatars.client import ApiClient
from avatars.constants import TypeResults
from avatars.models import FileAccess


class FileDownloader:
    def __init__(self, api_client: ApiClient):
        self.client = api_client

    def _download_with_credentials(self, file_access: FileAccess) -> str | bytes:
        """Download a file using credentials."""
        return self.client.download_file(file_access=file_access)

    def _download_file_to_str(self, url: str) -> str | bytes:
        """Get credentials for a URL and download the file."""
        file_access = self.client.results.get_permission_to_download(url)
        return self._download_with_credentials(file_access)

    def _str_to_json(self, str_data: str) -> list[dict[str, Any]]:
        if not str_data.strip().startswith("["):
            str_data = f"[{str_data}]"
        return json.loads(str_data)

    def _str_to_csv(self, str_data: str) -> pd.DataFrame:
        return pd.read_csv(io.StringIO(str_data))

    def _str_to_html(self, str_data: str) -> HTML:
        return HTML(str_data)

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
            case ".pdf" | ".docx":
                if path is None:
                    raise ValueError("Expected path to save the PDF file")
                if isinstance(str_data, bytes):
                    self._str_to_file(str_data, path)
                    data = f"Report saved successfully {path}"
            case ".html":
                if isinstance(str_data, str):
                    data = self._str_to_html(str_data)
        return data

    def download_file(self, url: str, path: str | None = None) -> TypeResults:
        """
        Download a file from the given URL and return its content in an appropriate format.
        If path is provided, save the file to that path.
        """
        str_data = self._download_file_to_str(url)
        extension = url.split(".")[-1]
        return self._str_to_results(str_data, f".{extension}", path)

    def download_files_batch(self, urls: list[str]) -> dict[str, TypeResults]:
        """
        Download multiple files from the given URLs using batch credential fetching.
        Returns a dictionary mapping URLs to their downloaded content.
        """
        if not urls:
            return {}

        # Get credentials for all files at once
        file_accesses = self.client.results.get_permissions_to_download_batch(urls)

        # Create a mapping of URL to FileAccess for easy lookup
        url_to_access = {access.url: access for access in file_accesses}

        # Download each file using the pre-fetched credentials
        results = {}
        for url in urls:
            if url in url_to_access:
                str_data = self._download_with_credentials(url_to_access[url])
                extension = url.split(".")[-1]
                results[url] = self._str_to_results(str_data, f".{extension}")
            # Skip files that failed permission check (not in url_to_access)

        return results
