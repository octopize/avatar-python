import pandas as pd
import io
from pathlib import Path
import tempfile
from typing import Any, Union
import httpx
from unittest.mock import patch
from uuid import uuid4

import pytest
from avatars.api import Datasets, PandasIntegration

from avatars.models import Dataset

from avatars.conftest import RequestHandle, api_client_factory


@pytest.fixture(scope="session")
def dataset_json() -> dict[str, Any]:
    return {
        "id": "5e27da4a-a5c5-458b-988e-ef2c66f545d6",
        "hash": "aeedab1ee7a1043753c9ab768594bc8420d7b85491d0be9421edc3813c237f4c",
        "name": "upload",
        "download_url": "http://localhost:8000/datasets/5e27da4a-a5c5-458b-988e-ef2c66f545d6/download",
        "nb_lines": 1,
        "nb_dimensions": 2,
        "filetype": "csv",
    }


class TestCustomCreateDatasetMethod:
    @pytest.fixture(scope="session")
    def create_dataset_response(self, dataset_json: dict[str, Any]) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=dataset_json)

        return handler

    def test_create_dataset_from_stream_deprecation(
        self, create_dataset_response: RequestHandle
    ) -> None:
        """Verify the call is deprecated, but it succeeds."""
        # TODO: remove this test when create_dataset_from_stream is removed
        client = api_client_factory(create_dataset_response)
        with pytest.deprecated_call(match="create_dataset_from_stream is deprecated"):
            dataset = Datasets(client).create_dataset_from_stream(
                request=io.BytesIO(b"Hello, world!")
            )

        assert dataset.id

    def test_create_dataset_request_argument_is_deprecated(
        self, create_dataset_response: RequestHandle
    ) -> None:
        """Verify the call is deprecated, but it succeeds."""
        client = api_client_factory(create_dataset_response)
        with pytest.deprecated_call(match="request is deprecated"):
            dataset = Datasets(client).create_dataset(request=io.BytesIO(b"123"))

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
        with pytest.raises(
            TypeError, match="Expected source to be a string or a buffer"
        ):
            Datasets(client).create_dataset(source=1)  # type:ignore[arg-type]

    def test_create_dataset_using_source_argument_with_filename(
        self, dataset_json: dict[str, Any]
    ) -> None:
        # Arrange
        client = api_client_factory()
        with tempfile.NamedTemporaryFile() as tmp_file, patch.object(
            client, "request", return_value=dataset_json
        ) as mock_request:
            Path(tmp_file.name).write_text("Hello, world!")
            # Act
            Datasets(client).create_dataset(source=tmp_file.name)

            # Assert
            mock_request.assert_called_once()
            file_ = mock_request.call_args.kwargs["file"][0][1]
            assert isinstance(file_, io.BufferedReader)

    @pytest.mark.filterwarnings(
        "ignore:You are trying to upload a text file:DeprecationWarning"
    )
    @pytest.mark.parametrize(
        "source",
        [io.BytesIO(b"Hello, world!"), io.StringIO("Hello, world!")],
    )
    def test_create_dataset_using_source_argument_with_buffer(
        self, source: io.IOBase, dataset_json: dict[str, Any]
    ) -> None:
        # Arrange
        client = api_client_factory()

        # Act
        with patch.object(client, "request", return_value=dataset_json) as mock_request:
            Datasets(client).create_dataset(source=source)

            # Assert
            mock_request.assert_called_once()
            file_ = mock_request.call_args.kwargs["file"][0][1]

            try:
                assert isinstance(file_, io.IOBase)  # BytesIO
            except AssertionError:
                assert isinstance(file_, tempfile._TemporaryFileWrapper)  # StringIO

    def test_create_dataset_using_source_argument_with_multiple_files(
        self, dataset_json: dict[str, Any]
    ) -> None:
        # Arrange
        client = api_client_factory()

        # Act
        with tempfile.TemporaryDirectory() as tmpdir:
            filename_1 = Path(tmpdir).joinpath("file1.txt")
            filename_2 = Path(tmpdir).joinpath("file2.txt")
            filename_1.write_text("Hello, world!")
            filename_2.write_text("Hello, world!")
            with patch.object(
                client, "request", return_value=dataset_json
            ) as mock_request:
                Datasets(client).create_dataset(
                    source=[str(filename_1), str(filename_2)]
                )

                # Assert
                mock_request.assert_called_once()
                files_ = mock_request.call_args.kwargs["file"]
                assert len(files_) == 2

                first_file_content = files_[0][1]
                second_file_content = files_[1][1]

                assert isinstance(first_file_content, io.BufferedReader)
                assert isinstance(second_file_content, io.BufferedReader)

    @pytest.mark.filterwarnings(
        "ignore:request is deprecated:DeprecationWarning"
    )  # TODO: Remove
    def test_create_dataset_with_deprecated_request_argument_calls_correct_request_method(
        self, create_dataset_response: RequestHandle, dataset_json: dict[str, Any]
    ) -> None:
        client = api_client_factory(create_dataset_response)

        with patch.object(client, "request", return_value=dataset_json) as mock_request:
            # as positional argument
            Datasets(client).create_dataset(io.BytesIO(b"123"))
            mock_request.assert_called_once()

            file_ = mock_request.call_args.kwargs["file"][0][1]

            assert isinstance(file_, io.BytesIO)

            mock_request.reset_mock()

            # as keyword argument
            Datasets(client).create_dataset(request=io.BytesIO(b"123"))
            mock_request.assert_called_once()

            file_ = mock_request.call_args.kwargs["file"][0][1]

            assert isinstance(file_, io.BytesIO)


class TestCustomDownloadDatasetMethod:
    @pytest.fixture(scope="session")
    def download_dataset_response(self) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"content": "Hello, world!"})

        return handler

    @pytest.fixture(scope="session")
    def download_dataset_streaming_response(self) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"Hello, world!")

        return handler

    def test_download_dataset_as_stream(
        self, download_dataset_streaming_response: RequestHandle
    ) -> None:
        """Verify the call is deprecated, but it succeeds."""
        # TODO: remove this test when download_dataset_as_stream is removed
        client = api_client_factory(download_dataset_streaming_response)
        with pytest.deprecated_call(match="download_dataset_as_stream is deprecated"):
            response = Datasets(client).download_dataset_as_stream(str(uuid4()))

        assert isinstance(response, io.BytesIO)
        assert response.read() == b"Hello, world!"

    def test_download_dataset_when_destination_is_none(
        self,
        download_dataset_streaming_response: RequestHandle,
    ) -> None:
        """Verify that we raise a DeprecationWarning, but keep the old behavior."""
        client = api_client_factory(download_dataset_streaming_response)
        with pytest.warns(
            DeprecationWarning, match="Please specify the destination argument"
        ):
            response = Datasets(client).download_dataset(
                str(uuid4()), destination=None, from_download_as_stream=False
            )
            assert isinstance(response, str)
            assert response == "Hello, world!"

    def test_download_dataset_with_valid_destination_as_filename(
        self,
        download_dataset_streaming_response: RequestHandle,
    ) -> None:
        """Verify that the method works correctly with a valid destination."""
        client = api_client_factory(download_dataset_streaming_response)
        with tempfile.NamedTemporaryFile() as tmp:
            Datasets(client).download_dataset(str(uuid4()), destination=tmp.name)
            assert Path(tmp.name).read_bytes() == b"Hello, world!"

    def test_download_dataset_with_invalid_destination(
        self,
        download_dataset_streaming_response: RequestHandle,
    ) -> None:
        """Verify that the method raises an error with an invalid destination."""
        client = api_client_factory(download_dataset_streaming_response)
        with pytest.raises(
            TypeError, match="Expected destination to be a string or a buffer"
        ):
            Datasets(client).download_dataset(str(uuid4()), destination=123)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "destination,expected",
        [
            (io.BytesIO(), b"Hello, world!"),
            (io.StringIO(), "Hello, world!"),
        ],
    )
    def test_download_dataset_with_valid_destination_as_buffer(
        self,
        download_dataset_streaming_response: RequestHandle,
        destination: Union[io.BytesIO, io.StringIO],
        expected: Union[bytes, str],
    ) -> None:
        """Verify that the method works correctly with a valid destination."""
        client = api_client_factory(download_dataset_streaming_response)
        dataset_id = str(uuid4())
        response = Datasets(client).download_dataset(
            dataset_id,
            destination=destination,
        )

        assert response is None
        assert destination.read() == expected


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
