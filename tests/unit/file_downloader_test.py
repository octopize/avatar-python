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
    api_client = FakeApiClient()
    downloader = FileDownloader(api_client)

    result = downloader.download_file(url=url, path="/tmp/test_file.pdf")

    assert isinstance(result, expected_type)

    if isinstance(expected_type, list):
        assert isinstance(result[0], dict)
