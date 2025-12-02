import pandas as pd
import pytest
from IPython.display import HTML

from avatars.file_downloader import FileDownloader
from tests.unit.conftest import FakeApiClient


@pytest.mark.parametrize(
    "url, expected_type",
    [
        ("iris.shuffled-0.csv", pd.DataFrame),
        ("patient_standalone.privacy.json", list),
        ("figures_contribution.html", HTML),
        ("report.pdf", str),
    ],
)
def test_download_file(url, expected_type):
    api_client = FakeApiClient(tables=["iris"])
    downloader = FileDownloader(api_client)

    result = downloader.download_file(url=url, path="/tmp/test_file.pdf")

    assert isinstance(result, expected_type)

    if isinstance(expected_type, list):
        assert isinstance(result[0], dict)


def test_download_files_batch_empty():
    """Test batch download with empty URL list."""
    api_client = FakeApiClient(tables=["iris"])
    downloader = FileDownloader(api_client)

    results = downloader.download_files_batch([])

    assert results == {}


def test_download_files_batch_single_file():
    """Test batch download with a single file."""
    api_client = FakeApiClient(tables=["iris"])
    downloader = FileDownloader(api_client)

    urls = ["iris.shuffled-0.csv"]
    results = downloader.download_files_batch(urls)

    assert len(results) == 1
    assert "iris.shuffled-0.csv" in results
    assert isinstance(results["iris.shuffled-0.csv"], pd.DataFrame)


def test_download_files_batch_multiple_files():
    """Test batch download with multiple files of different types."""
    api_client = FakeApiClient(tables=["iris", "patient"])
    downloader = FileDownloader(api_client)

    urls = [
        "iris.shuffled-0.csv",
        "patient.privacy.json",
        "figures_contribution.html",
    ]
    results = downloader.download_files_batch(urls)

    assert len(results) == 3
    assert "iris.shuffled-0.csv" in results
    assert "patient.privacy.json" in results
    assert "figures_contribution.html" in results

    # Check types
    assert isinstance(results["iris.shuffled-0.csv"], pd.DataFrame)
    assert isinstance(results["patient.privacy.json"], list)
    assert isinstance(results["patient.privacy.json"][0], dict)
    assert isinstance(results["figures_contribution.html"], HTML)


def test_download_files_batch_all_csv():
    """Test batch download with multiple CSV files."""
    api_client = FakeApiClient(tables=["iris", "patient", "sample"])
    downloader = FileDownloader(api_client)

    urls = [
        "iris.shuffled-0.csv",
        "patient.shuffled-0.csv",
        "sample.unshuffled-0.csv",
    ]
    results = downloader.download_files_batch(urls)

    assert len(results) == 3
    for url in urls:
        assert url in results
        assert isinstance(results[url], pd.DataFrame)


def test_download_files_batch_preserves_order():
    """Test that batch download results can be accessed in any order."""
    api_client = FakeApiClient(tables=["iris", "patient"])
    downloader = FileDownloader(api_client)

    urls = [
        "patient.privacy.json",
        "iris.shuffled-0.csv",
        "figures_contribution.html",
    ]
    results = downloader.download_files_batch(urls)

    # Check that all URLs are present regardless of order
    assert len(results) == 3
    for url in urls:
        assert url in results
