"""The `/access?url=` envelope serverless results are wrapped in, as on a server."""

from pathlib import Path

import pytest

from avatars.serverless.access import (
    SERVERLESS_BASE_URL,
    map_to_access_url,
    to_local_path,
    unwrap_access_url,
)


class TestAccessEnvelope:
    def test_round_trip(self) -> None:
        storage = "file:///tmp/results/standard/iris.shuffled-0.csv"
        envelope = map_to_access_url(SERVERLESS_BASE_URL, storage)
        assert unwrap_access_url(envelope) == storage

    def test_envelope_keeps_the_file_extension_last(self) -> None:
        """``FileDownloader`` reads the extension off the tail of the URL."""
        envelope = map_to_access_url(SERVERLESS_BASE_URL, "file:///a/b/x.parquet")
        assert envelope.rsplit(".", maxsplit=1)[-1] == "parquet"

    def test_envelope_keeps_the_filename_readable(self) -> None:
        """``ResultsOrganizer`` derives the table name from ``Path(url).stem``."""
        envelope = map_to_access_url(SERVERLESS_BASE_URL, "file:///a/iris.shuffled-0.csv")
        assert Path(envelope).stem.split(".shuffled")[0] == "iris"

    def test_a_storage_url_passes_through_unchanged(self) -> None:
        assert unwrap_access_url("file:///a/b.csv") == "file:///a/b.csv"

    def test_an_envelope_without_a_url_parameter_passes_through(self) -> None:
        assert unwrap_access_url("http://host/api/access") == "http://host/api/access"

    def test_only_one_layer_is_removed(self) -> None:
        inner = map_to_access_url(SERVERLESS_BASE_URL, "file:///a/b.csv")
        outer = map_to_access_url(SERVERLESS_BASE_URL, inner)
        assert unwrap_access_url(outer) == inner

    def test_to_local_path_strips_scheme_and_envelope(self) -> None:
        envelope = map_to_access_url(SERVERLESS_BASE_URL, "file:///tmp/x.csv")
        assert to_local_path(envelope) == "/tmp/x.csv"
        assert to_local_path("file:///tmp/x.csv") == "/tmp/x.csv"
        assert to_local_path("/tmp/x.csv") == "/tmp/x.csv"

    def test_base_url_never_resolves(self) -> None:
        """`.invalid` is reserved by RFC 6761, so a stray request fails loudly."""
        assert SERVERLESS_BASE_URL.endswith("/api")
        assert ".invalid" in SERVERLESS_BASE_URL

    @pytest.mark.parametrize("name", ["a+b", "a&b", "a#b", "50%", "a b", "caf\u00e9"])
    def test_a_path_with_reserved_characters_round_trips(self, name: str) -> None:
        storage = f"file:///tmp/{name}/results.json"
        envelope = map_to_access_url(SERVERLESS_BASE_URL, storage)
        assert unwrap_access_url(envelope) == storage
        assert to_local_path(envelope) == f"/tmp/{name}/results.json"

    @pytest.mark.parametrize("table", ["my table", "caf\u00e9", "patients_2024"])
    def test_a_table_name_stays_readable_at_the_end_of_the_url(self, table: str) -> None:
        """``ResultsOrganizer`` takes the table name from ``Path(url).stem``."""
        envelope = map_to_access_url(SERVERLESS_BASE_URL, f"file:///w/{table}.shuffled-0.csv")
        assert Path(envelope).stem.split(".shuffled")[0] == table
