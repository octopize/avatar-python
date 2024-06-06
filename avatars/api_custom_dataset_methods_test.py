import io
import os
import tempfile
from pathlib import Path
from typing import IO, Any, Dict, Iterator, Union
from unittest.mock import patch
from uuid import uuid4

import httpx
import pandas as pd
import pyarrow.dataset as ds
import pytest

from avatars.api import Datasets, PandasIntegration
from avatars.conftest import RequestHandle, api_client_factory
from avatars.models import Dataset, FileType

TEST_MAX_BYTES_PER_FILE = 1 * 1024  # 1 KB


@pytest.fixture(scope="session")
def dataset_json() -> dict[str, Any]:
    return {
        "id": "5e27da4a-a5c5-458b-988e-ef2c66f545d6",
        "hash": "aeedab1ee7a1043753c9ab768594bc8420d7b85491d0be9421edc3813c237f4c",
        "name": "upload",
        "download_url": "http://localhost:8000/datasets/5e27da4a-a5c5-458b-988e-ef2c66f545d6/download",  # noqa: E501
        "nb_lines": 1,
        "nb_dimensions": 2,
        "filetype": "csv",
    }


@pytest.fixture(scope="session")
def csv_content() -> bytes:
    return b"a,b\n1,2"


@pytest.fixture(scope="session")
def parquet_content(csv_content: bytes) -> bytes:
    result: bytes = pd.read_csv(io.BytesIO(csv_content)).to_parquet()
    return result


class TestCustomCreateDatasetMethod:
    @pytest.fixture(scope="session")
    def create_dataset_response(self, dataset_json: dict[str, Any]) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=dataset_json)

        return handler

    @pytest.fixture(scope="session")
    def large_csv(self) -> bytes:
        return b"a,b\n" + b"1,2\n" * TEST_MAX_BYTES_PER_FILE

    @pytest.mark.parametrize("content_fixture_name", ["csv_content", "parquet_content"])
    def test_create_dataset_from_stream(
        self,
        create_dataset_response: RequestHandle,
        content_fixture_name: str,
        request: Any,
    ) -> None:
        """Verify the call is deprecated, but it succeeds."""
        # TODO: remove this test when create_dataset_from_stream is removed
        content = request.getfixturevalue(content_fixture_name)
        client = api_client_factory(create_dataset_response)
        with pytest.deprecated_call(match="create_dataset_from_stream is deprecated"):
            dataset = Datasets(client).create_dataset_from_stream(
                request=io.BytesIO(content)
            )

        assert dataset.id

    @pytest.mark.parametrize("content_fixture_name", ["csv_content", "parquet_content"])
    def test_create_dataset_request_argument_is_deprecated(
        self,
        create_dataset_response: RequestHandle,
        content_fixture_name: str,
        request: Any,
    ) -> None:
        """Verify the parameter is deprecated, but it succeeds."""
        content = request.getfixturevalue(content_fixture_name)

        client = api_client_factory(create_dataset_response)
        with pytest.deprecated_call(match="request is deprecated"):
            dataset = Datasets(client).create_dataset(request=io.BytesIO(content))

        assert dataset.id

    @pytest.mark.filterwarnings(
        "ignore:request is deprecated:DeprecationWarning"
    )  # TODO: Remove
    def test_create_dataset_both_request_and_source_raises(self) -> None:
        client = api_client_factory()
        with pytest.raises(ValueError, match="You cannot pass both request and source"):
            Datasets(client).create_dataset(request=io.BytesIO(), source=io.BytesIO())

    def test_create_dataset_neither_request_nor_source_raises(self) -> None:
        client = api_client_factory()
        with pytest.raises(ValueError, match="You need to pass in a source"):
            Datasets(client).create_dataset()

    def test_create_dataset_with_unknown_source_type(self) -> None:
        client = api_client_factory()
        with pytest.raises(TypeError, match="Unsupported dataset source"):
            Datasets(client).create_dataset(source=1)

    @pytest.mark.parametrize("content_fixture_name", ["csv_content", "parquet_content"])
    def test_create_dataset_using_source_argument_with_filename(
        self,
        create_dataset_response: RequestHandle,
        content_fixture_name: str,
        request: Any,
    ) -> None:
        # Arrange
        content = request.getfixturevalue(content_fixture_name)
        client = api_client_factory(create_dataset_response)
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            result = Datasets(client).create_dataset(source=tmp_file.name)

        assert result.id

    @patch("avatars.api.MAX_BYTES_PER_FILE", TEST_MAX_BYTES_PER_FILE)
    @pytest.mark.parametrize(
        "filetype, buffer",
        [
            (FileType.csv, io.BytesIO),
            (FileType.csv, io.StringIO),  # TODO: Remove when request is deprecated
            (FileType.parquet, io.BytesIO),
        ],
    )
    def test_create_dataset_with_too_large_buffer_ok(
        self,
        create_dataset_response: RequestHandle,
        filetype: FileType,
        buffer: Any,
        large_csv: bytes,
    ) -> None:
        client = api_client_factory(create_dataset_response)

        filled_buffer: Union[io.BytesIO, io.StringIO]
        if filetype == FileType.csv:
            content = large_csv if buffer == io.BytesIO else large_csv.decode()
            filled_buffer = buffer(content)
        else:
            filled_buffer = buffer(pd.read_csv(io.BytesIO(large_csv)).to_parquet())

        filled_buffer.seek(0)
        # TODO: Remove the type ignore when request is deprecated
        # error: Argument "source" to "create_dataset" of "Datasets"
        #        has incompatible type "Union[BytesIO, StringIO]"; expected
        #        "Union[str, list[str], FileLikeInterface[bytes], None]"  [arg-type]
        res = Datasets(client).create_dataset(source=filled_buffer)
        assert res.id

    @patch("avatars.api.MAX_BYTES_PER_FILE", TEST_MAX_BYTES_PER_FILE)
    @pytest.mark.parametrize(
        "filetype, mode",
        [
            (
                FileType.csv,
                "rb",
            ),
            (FileType.parquet, "rb"),
        ],
        ids=str,
    )
    def test_create_dataset_with_too_large_file_ok(
        self,
        create_dataset_response: RequestHandle,
        filetype: FileType,
        mode: str,
        large_csv: bytes,
    ) -> None:
        client = api_client_factory(create_dataset_response)

        buffer = io.BytesIO(large_csv)
        buffer.seek(0)
        df = pd.read_csv(buffer)
        with tempfile.NamedTemporaryFile() as tmp_file:
            if filetype == FileType.parquet:
                df.to_parquet(tmp_file.name)
            else:
                df.to_csv(tmp_file.name)

            file_ = open(tmp_file.name, mode)
            res = Datasets(client).create_dataset(source=file_)
            assert res.id

    @pytest.mark.filterwarnings(
        "ignore:You are trying to upload a text file:DeprecationWarning"
    )
    @pytest.mark.parametrize("content_fixture_name", ["csv_content", "parquet_content"])
    @pytest.mark.parametrize("source", [io.BytesIO, io.StringIO])
    def test_create_dataset_using_source_argument_with_buffer(
        self,
        source: type[io.IOBase],
        content_fixture_name: str,
        create_dataset_response: RequestHandle,
        request: Any,
    ) -> None:
        if source == io.StringIO and content_fixture_name == "parquet_content":
            # We're skipping it here, because it makes it easier to handle a single test
            # with parametrized fixtures, rather than having to create a separate test
            # for each combination of source and content type.
            pytest.skip(
                "Parquet files are not UTF-8 encoded and cannot be read as a string."
            )

        client = api_client_factory(create_dataset_response)
        content = request.getfixturevalue(content_fixture_name)
        if source == io.StringIO:
            buffer = source(content.decode())  # type: ignore[call-arg]
        else:
            buffer = source(content)  # type: ignore[call-arg]

        res = Datasets(client).create_dataset(source=buffer)
        assert res.id

    def test_create_dataset_using_source_argument_with_multiple_files(
        self, create_dataset_response: RequestHandle, parquet_content: bytes
    ) -> None:
        # Arrange
        client = api_client_factory(create_dataset_response)

        # Act
        with tempfile.TemporaryDirectory() as tmpdir:
            filename_1 = Path(tmpdir).joinpath("file1.txt")
            filename_2 = Path(tmpdir).joinpath("file2.txt")
            filename_1.write_bytes(parquet_content)
            filename_2.write_bytes(parquet_content)
            res = Datasets(client).create_dataset(
                source=[str(filename_1), str(filename_2)]
            )
        assert res.id

    @pytest.mark.filterwarnings(
        "ignore:request is deprecated:DeprecationWarning"
    )  # TODO: Remove
    def test_create_dataset_with_deprecated_request_argument_calls_correct_request_method(
        self, create_dataset_response: RequestHandle, dataset_json: dict[str, Any]
    ) -> None:
        client = api_client_factory(create_dataset_response)

        with patch.object(client, "request", return_value=dataset_json) as mock_request:
            # as positional argument
            Datasets(client).create_dataset(io.BytesIO(b"123\n"))
            mock_request.assert_called_once()

            ds_ = mock_request.call_args.kwargs["dataset"]

            assert isinstance(ds_, ds.Dataset)

            mock_request.reset_mock()

            # as keyword argument
            Datasets(client).create_dataset(request=io.BytesIO(b"123\n"))
            mock_request.assert_called_once()

            ds_ = mock_request.call_args.kwargs["dataset"]

            assert isinstance(ds_, ds.Dataset)


@pytest.fixture(scope="session")
def download_dataset_parquet_response(parquet_content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=parquet_content,
        headers={"content-type": "application/octet-stream"},
    )


@pytest.fixture(scope="session")
def download_dataset_csv_response(csv_content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=csv_content,
        headers={"content-type": "text/csv"},
    )


@pytest.fixture(scope="session")
def get_dataset_response(dataset_json: Dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=dataset_json)


@pytest.fixture(scope="session")
def download_dataset_response(
    get_dataset_response: httpx.Response,
    download_dataset_parquet_response: httpx.Response,
    download_dataset_csv_response: httpx.Response,
) -> RequestHandle:
    def handler(request: httpx.Request) -> httpx.Response:
        is_download_dataset = "download" in request.url.path
        is_get_dataset = not is_download_dataset and request.url.path.startswith(
            "/datasets"
        )
        if is_download_dataset:
            is_parquet_filetype = b"parquet" in request.url.query
            if is_parquet_filetype:
                return download_dataset_parquet_response
            else:
                return download_dataset_csv_response
        elif is_get_dataset:
            return get_dataset_response
        else:
            raise ValueError("Unexpected request")

    return handler


class TestCustomDownloadDatasetMethod:
    @pytest.mark.parametrize(
        "filetype,expected_output_fixture_name",
        [
            (FileType.csv, "csv_content"),
            (FileType.parquet, "parquet_content"),
        ],
    )
    def test_download_dataset_as_stream(
        self,
        download_dataset_response: RequestHandle,
        filetype: FileType,
        expected_output_fixture_name: str,
        request: Any,
    ) -> None:
        """Verify the call is deprecated, but it succeeds."""
        # TODO: remove this test when download_dataset_as_stream is removed
        client = api_client_factory(download_dataset_response)
        with pytest.deprecated_call(match="download_dataset_as_stream is deprecated"):
            response = Datasets(client).download_dataset_as_stream(
                str(uuid4()), filetype=filetype
            )

        expected = request.getfixturevalue(expected_output_fixture_name)
        assert isinstance(response, io.BytesIO)
        assert response.read() == expected

    @pytest.mark.parametrize(
        "filetype,expected_output_fixture_name",
        [
            (FileType.csv, "csv_content"),
            (None, "csv_content"),  # old behavior
        ],
    )
    def test_download_dataset_when_destination_is_none(
        self,
        download_dataset_response: RequestHandle,
        filetype: FileType,
        expected_output_fixture_name: str,
        request: Any,
    ) -> None:
        """Verify that we raise a DeprecationWarning, but keep the old behavior."""
        client = api_client_factory(download_dataset_response)
        with pytest.warns(
            DeprecationWarning, match="Please specify the destination argument"
        ):
            response = Datasets(client).download_dataset(
                str(uuid4()),
                destination=None,
                from_download_as_stream=False,
                filetype=filetype,
            )

            expected: bytes = request.getfixturevalue(expected_output_fixture_name)
            assert isinstance(response, str)
            assert response == expected.decode()

    @pytest.mark.parametrize(
        "filetype,expected_output_fixture_name",
        [
            (FileType.csv, "csv_content"),
            (FileType.parquet, "parquet_content"),
        ],
    )
    def test_download_dataset_with_valid_destination_as_filename(
        self,
        download_dataset_response: RequestHandle,
        filetype: FileType,
        expected_output_fixture_name: str,
        request: Any,
    ) -> None:
        """Verify that the method works correctly with a valid destination."""
        client = api_client_factory(download_dataset_response)
        with tempfile.NamedTemporaryFile() as tmp:
            Datasets(client).download_dataset(
                str(uuid4()), destination=tmp.name, filetype=filetype
            )

            expected: bytes = request.getfixturevalue(expected_output_fixture_name)
            assert Path(tmp.name).read_bytes() == expected

    @pytest.fixture(scope="function")
    def binary_file_handle(self) -> Iterator[IO[bytes]]:
        new_file = tempfile.NamedTemporaryFile("rb+")
        yield new_file
        new_file.close()

    @pytest.fixture(scope="function")
    def file_handle(self) -> Iterator[IO[str]]:
        new_file = tempfile.NamedTemporaryFile("r+")
        yield new_file
        new_file.close()

    @pytest.mark.parametrize(
        "filetype,expected_output_fixture_name,destination",
        [
            pytest.param(
                FileType.csv, "csv_content", io.BytesIO(), id="io.BytesIO-csv"
            ),
            pytest.param(
                FileType.csv, "csv_content", io.StringIO(), id="io.StringIO-csv"
            ),
            pytest.param(FileType.csv, "csv_content", "binary_file_handle"),
            pytest.param(FileType.csv, "csv_content", "file_handle"),
            pytest.param(
                FileType.parquet,
                "parquet_content",
                io.BytesIO(),
                id="io.BytesIO-parquet",
            ),
            pytest.param(FileType.parquet, "parquet_content", "binary_file_handle"),
        ],
    )
    def test_download_dataset_with_valid_destination_as_buffer(
        self,
        download_dataset_response: RequestHandle,
        destination: Union[str, IO[bytes], IO[str]],
        filetype: FileType,
        expected_output_fixture_name: str,
        request: Any,
    ) -> None:
        """Verify that the method works correctly with a valid destination."""
        client = api_client_factory(download_dataset_response)
        dataset_id = str(uuid4())

        # grab the open file handle fixture
        destination = (
            request.getfixturevalue(destination)
            if isinstance(destination, str)
            else destination
        )

        response = Datasets(client).download_dataset(
            dataset_id,
            destination=destination,
            filetype=filetype,
        )

        assert response is None

        expected: bytes = request.getfixturevalue(expected_output_fixture_name)

        destination.seek(0, os.SEEK_SET)
        actual = destination.read()
        actual = actual if isinstance(actual, bytes) else actual.encode()

        assert actual == expected

    def test_download_dataset_with_invalid_destination_fails(
        self,
        download_dataset_response: RequestHandle,
    ) -> None:
        """Verify that the method raises an error with an invalid destination."""
        client = api_client_factory(download_dataset_response)
        with pytest.raises(
            TypeError, match="Expected destination to be a string or a buffer"
        ):
            Datasets(client).download_dataset(
                str(uuid4()),
                destination=123,  # type: ignore[arg-type]
            )


class TestPandasIntegrationUploadDataframe:
    @pytest.fixture
    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

    @pytest.fixture(scope="session")
    def create_dataset_response(self, dataset_json: dict[str, Any]) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=dataset_json)

        return handler

    @pytest.mark.filterwarnings(
        "ignore:You are trying to upload a text file:DeprecationWarning"
    )
    def test_upload_dataframe(
        self, dataframe: pd.DataFrame, create_dataset_response: RequestHandle
    ) -> None:
        # Arrange
        client = api_client_factory(create_dataset_response)
        # Act
        result = PandasIntegration(client).upload_dataframe(dataframe)
        # Assert
        assert isinstance(result, Dataset)


class TestPandasIntegrationDownloadDataframe:
    @pytest.fixture
    def dataset(self, dataset_json: dict[str, Any]) -> Dataset:
        return Dataset(**dataset_json)

    @pytest.fixture(scope="session")
    def dataframe(self, csv_content: bytes) -> pd.DataFrame:
        return pd.read_csv(io.BytesIO(csv_content))

    @pytest.mark.filterwarnings(
        "ignore:download_dataset_as_stream is deprecated:DeprecationWarning"
    )
    def test_download_dataframe(
        self,
        download_dataset_response: RequestHandle,
        dataset: Dataset,
        dataframe: pd.DataFrame,
    ) -> None:
        """Verify the call is deprecated, but it succeeds."""
        client = api_client_factory(download_dataset_response)
        with pytest.deprecated_call(
            match="The `should_stream` parameter is deprecated"
        ):
            result = PandasIntegration(client).download_dataframe(
                str(dataset.id), should_stream=True
            )

        pd.testing.assert_frame_equal(result, dataframe)
