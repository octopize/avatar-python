"""Error reporting, exercised without the engine.

``map_engine_exception`` matches on the exception's class *name* precisely so these
can be written against synthetic exceptions. The wording is not cosmetic: the server
produces these exact strings, ``Runner`` renders ``job.exception`` verbatim, and
support answers are written against them.
"""

from pathlib import Path

import pytest

from avatars.models import JobStatus
from avatars.serverless.executor import map_engine_exception, write_traceback


def raise_as(name: str, message: str) -> Exception:
    """An exception whose *class name* is what the mapper keys on."""
    exception_type: type[Exception] = type(name, (Exception,), {})
    return exception_type(message)


class TestLicenceErrors:
    def test_wording_matches_the_api_verbatim(self) -> None:
        status, message = map_engine_exception("standard", raise_as("LicenseError", "nope"))
        assert status == JobStatus.error
        assert message == (
            "Error in job 'standard': Your license does not allow you to access these features."
        )

    @pytest.mark.parametrize("code", ["AVTR-LIC-003", "AVTR-LIC-005", "AVTR-LIC-006"])
    def test_a_stable_licence_code_is_kept(self, code: str) -> None:
        """An expired build or licence is not a feature the licence lacks: say which."""
        _, message = map_engine_exception(
            "standard", raise_as("LicenseError", f"{code} internal detail /opt/x")
        )
        assert message.endswith(f"({code})")
        assert "internal detail" not in message

    def test_the_engine_message_is_not_leaked(self) -> None:
        """The server deliberately replaces it; the raw message names internals."""
        _, message = map_engine_exception("standard", raise_as("LicenseError", "feature xyz"))
        assert "xyz" not in message


class TestSizeLimits:
    @pytest.mark.parametrize("name", ["TooManyLinesError", "TooManyDimensionsError"])
    def test_presented_as_a_licence_limit_with_the_engine_detail_kept(self, name: str) -> None:
        status, message = map_engine_exception("standard", raise_as(name, "1000 > 100"))
        assert status == JobStatus.error
        assert message.startswith("This dataset is too large for your current license.")
        assert "1000 > 100" in message
        assert message.endswith("Upgrade your plan to process larger datasets.")


class TestFileErrors:
    def test_missing_input_tells_the_user_to_upload(self) -> None:
        _, message = map_engine_exception("standard", raise_as("CustomFileNotFoundError", "a.csv"))
        assert message == "file a.csv not found, try to upload it first"

    def test_missing_report_input_points_at_the_folder(self) -> None:
        _, message = map_engine_exception(
            "report", raise_as("CustomReportFileNotFoundError", "/a/b/results.json")
        )
        assert "/a/b" in message
        assert "depends_on" in message


class TestMemory:
    def test_out_of_memory_is_explained_in_serverless_terms(self) -> None:
        """There is no worker to kill in-process, so the server's KilledWorker advice
        ('contact support to resize the cluster') would be misleading.
        """
        _, message = map_engine_exception("standard", MemoryError())
        assert "ran out of memory" in message
        assert "server deployment" in message


class TestUnknown:
    def test_falls_back_to_the_type_and_message(self) -> None:
        status, message = map_engine_exception("standard", ValueError("something odd"))
        assert status == JobStatus.error
        assert message == "ValueError: something odd"


class TestTraceback:
    def test_written_with_the_type_and_the_stack(self, tmp_path: Path) -> None:
        log = tmp_path / "logs" / "job.log"
        try:
            raise ValueError("boom")
        except ValueError as exc:
            write_traceback(log, "job", exc)
        content = log.read_text()
        assert "ValueError" in content
        assert "boom" in content

    def test_an_unwritable_location_does_not_turn_one_failure_into_another(
        self, tmp_path: Path
    ) -> None:
        unwritable = tmp_path / "file"
        unwritable.write_text("not a directory")
        write_traceback(unwritable / "nested" / "job.log", "job", ValueError("boom"))
