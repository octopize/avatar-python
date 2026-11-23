import io
from typing import BinaryIO
from urllib.parse import parse_qs

import pandas as pd
from pydantic_core import Url
from structlog import get_logger

from avatars import presigned_transfer
from avatars.base_client import ApiResponseError
from avatars.input_files import InputFiles, input_files_listing
from avatars.models import FileAccess
from avatars.sdk_client import SdkClient
from avatars.storage import get_filesystem, get_parent

logger = get_logger(__name__)


class DataUploader:
    def __init__(
        self,
        api_client: SdkClient,
        storage_endpoint_url: str,
        should_verify_ssl: bool = True,
    ) -> None:
        """Move files between the caller and the platform's storage.

        Two transports, chosen by ``api_client.storage_transport``:

        * credentials (the default): ask the API for S3 credentials scoped to
          the user, then talk to the storage endpoint with an S3 client. Needs
          ``storage_endpoint_url`` to be reachable and correct.
        * pre-signed URLs: ask the API to sign one request for one object, then
          PUT or GET that URL over plain HTTP. Needs no storage configuration
          at all — the URL carries the endpoint — and no S3 credential ever
          reaches this process.

        ``storage_endpoint_url`` is still required in both cases so that falling
        back to credentials is always possible without re-configuring the client.

        One call cannot be a grant: ``list_input_files`` lists a directory, and a
        signature covers one object, so there is nothing to sign for it. On the
        pre-signed transport the API answers the listing instead, and only on
        credentials does the client list the storage itself.
        """
        if not storage_endpoint_url:
            raise ValueError("storage_endpoint_url must be provided to DataUploader")

        self.api_client = api_client
        self.should_verify_ssl = should_verify_ssl or self.api_client.should_verify_ssl
        self.storage_endpoint_url = storage_endpoint_url

        logger.debug(
            "datauploader initialized",
            storage_endpoint_url=storage_endpoint_url,
        )

    def upload_file(self, data: str | pd.DataFrame, key: str) -> None:
        """Upload a file to the storage.

        Parameters
        ----------
        data :
            a path to a file or a pandas dataframe to upload
        key :
            name of the file where it should be uploaded; a file of that name already
            in the storage is overwritten

        """
        if isinstance(data, str):
            with open(data, "rb") as fd:
                self.upload_file_descriptor(fd, key)
        elif isinstance(data, pd.DataFrame):
            binary_stream = io.BytesIO()
            data.reset_index(drop=True).to_parquet(binary_stream, index=False)
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

        transport = self.api_client.storage_transport
        if transport.is_presigned():
            try:
                grant = self.api_client.results.get_presigned_url(
                    url=user_specific_path, method="put"
                )
            except ApiResponseError as error:
                if not transport.falls_back_on(error):
                    raise
            else:
                presigned_transfer.upload(
                    grant.presigned_url,
                    content,
                    should_verify_ssl=self.should_verify_ssl,
                )
                return None

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

        return fsspec_fs.write_bytes(user_specific_path, content)  # type: ignore[no-any-return]

    def list_input_files(self) -> InputFiles:
        """List the files of your input directory, newest first.

        A listed file can be given to ``Runner.add_table`` in place of the data, so
        the table reads it from the storage and nothing is uploaded again.

        A listing names no object, and a pre-signed URL grants exactly one, so
        there is nothing to sign for it. On the pre-signed transport the API
        lists the directory instead, with `/input_files`; on credentials the
        client lists the storage itself, as it always has.
        """
        transport = self.api_client.storage_transport
        if transport.is_presigned():
            try:
                return self._list_through_the_api()
            except ApiResponseError as error:
                # Not ``falls_back_on``: that one would record that this server
                # cannot sign, and send every later transfer of the session to
                # the storage endpoint with a credential. A server that signs
                # but is too old to list is still a server that signs.
                if not transport.tolerates_a_missing_route(error):
                    raise
                logger.warning("this server does not list input files, listing the storage")

        return self._list_with_credentials()

    def _list_through_the_api(self) -> InputFiles:
        """The listing the API computes, for a client that holds no S3 credential."""
        directory = self.api_client.results.get_upload_url()
        return input_files_listing(
            directory,
            [
                {
                    "name": file.name,
                    "size": file.size,
                    "LastModified": file.last_modified,
                }
                for file in self.api_client.results.get_input_files()
            ],
        )

    def _list_with_credentials(self) -> InputFiles:
        directory = self.api_client.results.get_upload_url()
        access_url = f"{self.api_client.base_url}/access?url=" + directory
        credentials = self.api_client.results.get_permission_to_download(access_url).credentials
        fsspec_fs = get_filesystem(
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_access_key,
            storage_path=directory,
            storage_endpoint_url=self.storage_endpoint_url,
            should_verify_ssl=self.should_verify_ssl,
        )
        try:
            entries = fsspec_fs.ls(directory, detail=True, refresh=True)
        except FileNotFoundError:
            entries = []
        return input_files_listing(directory, entries)

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

        output: str | bytes
        if _is_binary(parsed_download):
            output = fs.read_bytes(parsed_download)
        else:
            output = fs.read_text(parsed_download, encoding="utf-8")

        return output


# Which results are handed back as bytes and which as text. Kept in one place so
# the credentialed and pre-signed paths cannot disagree about a file type.
BINARY_SUFFIXES = (".pdf", ".docx", ".parquet")


def _is_binary(url: str) -> bool:
    return url.endswith(BINARY_SUFFIXES)


def decode_result(url: str, content: bytes) -> str | bytes:
    r"""Bytes for a binary result, decoded text for everything else.

    Decoded through :class:`io.TextIOWrapper` rather than :meth:`bytes.decode`,
    because the credentialed path reads text with ``fsspec``'s ``read_text``,
    which wraps the file in one with ``newline=None`` and so turns ``\r\n`` and
    ``\r`` into ``\n``. A plain decode keeps them, and the same result would
    then read differently depending on which transport the deployment uses.
    """
    if _is_binary(url):
        return content
    return io.TextIOWrapper(io.BytesIO(content), encoding="utf-8", newline=None).read()
