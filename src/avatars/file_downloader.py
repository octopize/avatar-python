import io
import json

import pandas as pd
from IPython.display import HTML

from avatars.client import ApiClient
from avatars.constants import TypeResults


class FileDownloader:
    def __init__(self, api_client: ApiClient):
        self.client = api_client

    def _download_file_to_str(self, url: str) -> str | bytes:
        fileaccess = self.client.results.get_permission_to_download(url)
        data_str = self.client.download_file(file_access=fileaccess)
        return data_str

    def _str_to_json(self, str_data: str) -> list[dict]:
        if not str_data.strip().startswith("["):
            str_data = f"[{str_data}]"
        return json.loads(str_data)

    def _str_to_csv(self, str_data: str) -> pd.DataFrame:
        return pd.read_csv(io.StringIO(str_data))

    def _str_to_html(self, str_data: str) -> HTML:
        return HTML(str_data)

    def _str_to_pdf(self, str_data: bytes, path: str) -> None:
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
            case ".pdf":
                if path is None:
                    raise ValueError("Expected path to save the PDF file")
                if isinstance(str_data, bytes):
                    self._str_to_pdf(str_data, path)
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
