from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from avatars.data_upload import DataUploader
from avatars.input_files import InputFile, InputFiles, input_files_listing, retention_days_of
from tests.unit.conftest import FakeApiClient

UPLOAD_DIRECTORY = "s3://user-bucket/30d/org/user/input"


class TestRetentionDays:
    def test_reads_the_first_segment_of_the_key(self) -> None:
        assert retention_days_of(UPLOAD_DIRECTORY) == 30

    def test_none_without_a_retention_segment(self) -> None:
        assert retention_days_of("s3://user-bucket/org/user/input") is None
        assert retention_days_of("file:///tmp/uploads") is None
        assert retention_days_of("s3://user-bucket") is None


class TestInputFilesListing:
    def test_files_are_named_without_the_directory_and_newest_first(self) -> None:
        older = datetime(2026, 1, 1, tzinfo=UTC)
        newer = datetime(2026, 1, 2, tzinfo=UTC)
        files = input_files_listing(
            UPLOAD_DIRECTORY,
            [
                {"name": "user-bucket/30d/org/user/input/a.csv", "size": 1, "LastModified": older},
                {"name": "user-bucket/30d/org/user/input/b.csv", "size": 2, "LastModified": newer},
                {"name": "user-bucket/30d/org/user/input/sub", "size": 0, "type": "directory"},
            ],
        )
        assert list(files) == ["b.csv", "a.csv"]
        assert files["a.csv"] == InputFile(
            name="a.csv", size=1, uploaded_at=older, expires_at=older + timedelta(days=30)
        )
        assert files.retention_days == 30

    def test_local_timestamps_and_unknown_retention(self) -> None:
        files = input_files_listing(
            "file:///tmp/uploads",
            [{"name": "/tmp/uploads/a.csv", "size": 1, "type": "file", "mtime": 0.0}],
        )
        assert files["a.csv"].uploaded_at == datetime(1970, 1, 1, tzinfo=UTC)
        assert files["a.csv"].expires_at is None
        assert files.retention_days is None

    def test_a_file_without_a_time_sorts_last(self) -> None:
        dated = InputFile("dated.csv", uploaded_at=datetime(2026, 1, 1, tzinfo=UTC))
        files = InputFiles([InputFile("undated.csv"), dated])
        assert list(files) == ["dated.csv", "undated.csv"]

    def test_a_missing_name_lists_the_stored_files(self) -> None:
        files = InputFiles([InputFile("a.csv"), InputFile("b.parquet")])
        with pytest.raises(KeyError, match=r"'c.csv'.*Stored files: a.csv, b.parquet"):
            files["c.csv"]

    def test_mapping_protocol(self) -> None:
        files = InputFiles([InputFile("a.csv")])
        assert len(files) == 1
        assert "a.csv" in files
        assert repr(files) == "InputFiles(['a.csv'])"


class TestDataUploaderListing:
    """``list_input_files`` against a local directory in place of the object storage."""

    @pytest.fixture
    def upload_directory(self, tmp_path: Path) -> Path:
        return tmp_path / "uploads"

    @pytest.fixture
    def data_uploader(self, tmp_path: Path, upload_directory: Path) -> DataUploader:
        api_client = FakeApiClient()
        api_client.results._upload_url_base = upload_directory.as_uri()  # type: ignore[attr-defined]
        return DataUploader(api_client, storage_endpoint_url=tmp_path.as_uri())

    def test_lists_what_was_uploaded(
        self, data_uploader: DataUploader, upload_directory: Path
    ) -> None:
        data_uploader.upload_file(pd.DataFrame({"a": [1, 2]}), "patients.parquet")
        (upload_directory / "visits.csv").write_text("a,b\n1,2\n")

        files = data_uploader.list_input_files()

        assert set(files) == {"patients.parquet", "visits.csv"}
        assert files["visits.csv"].size == 8
        assert files["visits.csv"].uploaded_at is not None

    def test_a_second_upload_under_the_same_name_overwrites_the_file(
        self, data_uploader: DataUploader, upload_directory: Path
    ) -> None:
        data_uploader.upload_file(pd.DataFrame({"a": [1, 2]}), "patients.parquet")
        data_uploader.upload_file(pd.DataFrame({"a": [3]}), "patients.parquet")

        assert list(data_uploader.list_input_files()) == ["patients.parquet"]
        assert pd.read_parquet(upload_directory / "patients.parquet")["a"].tolist() == [3]

    def test_an_empty_or_missing_directory_lists_nothing(
        self, data_uploader: DataUploader
    ) -> None:
        assert list(data_uploader.list_input_files()) == []
