import io
from typing import BinaryIO
from urllib.parse import parse_qs

import pandas as pd
from pydantic_core import Url
from structlog import get_logger

from avatars.client import ApiClient
from avatars.models import FileAccess
from avatars.storage import get_filesystem, get_parent

logger = get_logger(__name__)


class DataUploader:
    def __init__(
        self,
        api_client: ApiClient,
        storage_endpoint_url: str,
        should_verify_ssl: bool = True,
    ) -> None:
        if not storage_endpoint_url:
            raise ValueError("storage_endpoint_url must be provided to DataUploader")

        self.api_client = api_client
        self.should_verify_ssl = should_verify_ssl or self.api_client.should_verify_ssl
        self.storage_endpoint_url = storage_endpoint_url

        logger.debug("datauploader initialized", storage_endpoint_url=storage_endpoint_url)

    def upload_file(self, data: str | pd.DataFrame, key: str) -> None:
        """Upload a file to the storage.
        Parameters
        ----------
        data :
            a path to a file or a pandas dataframe to upload
        key :
            name of the file where it should be uploaded
        """
        if isinstance(data, str):
            with open(data, "rb") as fd:
                self.upload_file_descriptor(fd, key)
        elif isinstance(data, pd.DataFrame):
            binary_stream = io.BytesIO()
            data.reset_index(drop=True).to_csv(binary_stream, index=False)
            binary_stream.seek(0)
            self.upload_file_descriptor(binary_stream, key)
        else:
            raise ValueError(
                f"Expected a path to a file or a pandas dataframe to upload, got {type(data)}"
            )

    def upload_file_descriptor(self, fd: BinaryIO, key: str) -> None:
        """Upload a file descriptor to the storage.

        Parameters
        ----------
        fd :
            File descriptor to upload
        key :
            Relative filepath where the file should be uploaded
        """
        content = fd.read()
        base = self.api_client.results.get_upload_url()
        user_specific_path = base + f"/{key}"
        access_url = f"{self.api_client.base_url}/access?url=" + user_specific_path
        credentials = self.api_client.results.get_permission_to_download(access_url).credentials
        fsspec_fs = get_filesystem(
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_access_key,
            storage_path=user_specific_path,
            storage_endpoint_url=self.storage_endpoint_url,
            should_verify_ssl=self.should_verify_ssl,
        )

        parent = get_parent(user_specific_path)
        fsspec_fs.makedirs(parent, exist_ok=True)

        return fsspec_fs.write_bytes(user_specific_path, content)  # type: ignore[no-any-return] # noqa: E501

    def download_file(self, file_access: FileAccess) -> str | bytes:
        """Download content from the storage to a file.
        Parameters
        ----------
        file_access :
            File access object containing the url and credentials
        path :
            Relative filepath where the file should be downloaded
        """
        download_url = file_access.url
        credentials = file_access.credentials
        parsed_download = parse_qs(Url(download_url).query).get("url", [""])[0]
        fs = get_filesystem(
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_access_key,
            storage_path=parsed_download,
            storage_endpoint_url=self.storage_endpoint_url,
            should_verify_ssl=self.should_verify_ssl,
        )

        if parsed_download.endswith(".pdf") or parsed_download.endswith(".docx"):
            output = fs.read_bytes(parsed_download)
        else:
            output = fs.read_text(parsed_download, encoding="utf-8")

        return output
