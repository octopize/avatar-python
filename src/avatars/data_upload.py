import io
from typing import BinaryIO
from urllib.parse import parse_qs
from uuid import UUID

import pandas as pd
from pydantic_core import Url

from avatars.client import ApiClient
from avatars.models import FileAccess
from avatars.storage import get_filesystem, get_parent


class DataUploader:
    def __init__(
        self,
        api_client: ApiClient,
        user_id: UUID | None = None,  # for testing
    ) -> None:
        if api_client is None and user_id is None:
            raise ValueError("Either api_client or user_id must be provided")

        self.api_client = api_client
        self.user_id = user_id

    def _get_own_user_id(self) -> UUID:
        return self.api_client.users.get_me().id

    def _get_user_id(self) -> UUID:
        if self.user_id:
            return self.user_id

        if self.api_client.auth_tokens is None:
            raise ValueError("ApiClient is not authenticated")

        self.user_id = self._get_own_user_id()
        return self.user_id

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
        )

        if parsed_download.endswith(".pdf"):
            output = fs.read_bytes(parsed_download)
        else:
            output = fs.read_text(parsed_download)

        return output
