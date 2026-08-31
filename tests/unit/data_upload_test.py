from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from avatars.data_upload import DataUploader
from tests.unit.conftest import FakeApiClient


class TestDataUploader:
    """Tests for DataUploader.upload_file() and download_file() using actual filesystem."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for storage."""
        with TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def api_client(self):
        """Create a FakeApiClient."""
        return FakeApiClient()

    @pytest.fixture
    def data_uploader(self, api_client, temp_dir):
        """Create a DataUploader instance with local filesystem."""
        file_url = Path(temp_dir).as_uri()
        api_client.results._upload_url_base = file_url + "/uploads"
        return DataUploader(
            api_client,
            storage_endpoint_url=file_url,
            should_verify_ssl=False,
        )

    # Upload tests with different extensions
    def test_upload_dataframe_as_parquet(self, data_uploader, temp_dir):
        """Test uploading DataFrame as parquet."""
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        data_uploader.upload_file(df, "test.parquet")
        stored_file = Path(temp_dir) / "uploads" / "test.parquet"
        assert stored_file.exists()
        assert pd.read_parquet(stored_file).shape == (3, 2)

    def test_upload_file_from_path_csv(self, data_uploader, temp_dir):
        """Test uploading file from filesystem path (CSV)."""
        # Create a CSV file to upload
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["x", "y", "z"]})
        csv_file = Path(temp_dir) / "source.csv"
        df.to_csv(csv_file, index=False)

        # Upload the CSV file
        data_uploader.upload_file(str(csv_file), "uploaded.csv")

        # Verify file was uploaded
        uploaded_file = Path(temp_dir) / "uploads" / "uploaded.csv"
        assert uploaded_file.exists()
        # Verify content matches
        uploaded_df = pd.read_csv(uploaded_file)
        pd.testing.assert_frame_equal(uploaded_df, df)

    def test_upload_file_from_path_parquet(self, data_uploader, temp_dir):
        """Test uploading file from filesystem path (parquet)."""
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["x", "y", "z"]})
        parquet_file = Path(temp_dir) / "source.parquet"
        df.to_parquet(parquet_file, index=False)

        data_uploader.upload_file(str(parquet_file), "uploaded.parquet")

        uploaded_file = Path(temp_dir) / "uploads" / "uploaded.parquet"
        assert uploaded_file.exists()
        uploaded_df = pd.read_parquet(uploaded_file)
        pd.testing.assert_frame_equal(uploaded_df, df)
