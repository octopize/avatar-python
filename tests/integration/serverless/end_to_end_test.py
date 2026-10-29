"""Serverless mode against the real engine, with no server running.

Skipped unless the engine is installed, which is also what makes this file harmless
in the public ``octopize/avatar-python`` mirror, where the extra cannot be resolved.

Run locally with::

    just install-serverless && just test-serverless
"""

import io
import shutil
import threading
import zipfile
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

pytest.importorskip(
    "avatar",
    reason="needs the engine: `just install-serverless`, or an engine bundle",
)

from avatar.models.feature_scope import FeatureScope, LicenseError
from avatar_yaml.models.parameters import ReportType

from avatars import Manager
from avatars.models import JobKind
from avatars.serverless.config import ServerlessConfig

pytestmark = [
    pytest.mark.serverless,
    # The engine's stack (pandas 3, pyarrow, dask) emits warnings the client's global
    # `filterwarnings = ["error"]` would turn into failures. Relaxed here only --
    # loosening it globally would weaken every existing unit test.
    pytest.mark.filterwarnings("default"),
]

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture
def iris() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "iris.csv")


@pytest.fixture
def manager(tmp_path: Path, license_key: str) -> Manager:
    return Manager(serverless=True, license_key=license_key, workdir=tmp_path / "wd")


def test_single_table_avatarization_and_metrics(manager: Manager, iris: pd.DataFrame) -> None:
    """The flow from the brief: no server, no second process, inside one kernel."""
    runner = manager.create_runner("iris_serverless")
    runner.add_table("iris", data=iris)
    runner.set_parameters("iris", k=5, ncp=2)
    runner.run([JobKind.standard, JobKind.signal_metrics, JobKind.privacy_metrics])

    assert runner.get_status(JobKind.standard) == "finished"
    assert runner.get_status(JobKind.signal_metrics) == "finished"
    assert runner.get_status(JobKind.privacy_metrics) == "finished"

    shuffled = runner.shuffled("iris")
    assert isinstance(shuffled, pd.DataFrame)
    assert shuffled.shape == iris.shape
    assert list(shuffled.columns) == list(iris.columns)

    privacy = runner.privacy_metrics("iris")
    assert privacy
    assert "hidden_rate" in privacy[0]

    signal = runner.signal_metrics("iris")
    assert signal


def test_nothing_was_written_outside_the_workdir(
    manager: Manager, iris: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serverless must be self-contained: no stray results in the CWD."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    runner = manager.create_runner("iris_serverless")
    runner.add_table("iris", data=iris)
    runner.set_parameters("iris", k=5, ncp=2)
    runner.run([JobKind.standard])

    assert not list(cwd.iterdir()), sorted(p.name for p in cwd.iterdir())
    workdir = tmp_path / "wd"
    assert (workdir / "index.json").is_file()
    assert list((workdir / "input").iterdir())
    assert list((workdir / "sets").iterdir())


def test_the_same_seed_reproduces_the_same_avatars(
    tmp_path: Path, iris: pd.DataFrame, license_key: str
) -> None:
    """Both runs share a workdir, so they share the persisted seeding salt."""
    workdir = tmp_path / "wd"
    frames = []
    for name in ("first", "second"):
        runner = Manager(serverless=True, license_key=license_key, workdir=workdir).create_runner(
            name, seed=42
        )
        runner.add_table("iris", data=iris)
        runner.set_parameters("iris", k=5, ncp=2)
        runner.run([JobKind.standard])
        frames.append(runner.shuffled("iris"))

    pd.testing.assert_frame_equal(frames[0], frames[1])


def test_results_survive_a_new_manager_on_the_same_workdir(
    tmp_path: Path, iris: pd.DataFrame, license_key: str
) -> None:
    """The kernel-restart case, which in a notebook is the normal one."""
    workdir = tmp_path / "wd"
    runner = Manager(serverless=True, license_key=license_key, workdir=workdir).create_runner(
        "iris_serverless"
    )
    runner.add_table("iris", data=iris)
    runner.set_parameters("iris", k=5, ncp=2)
    runner.run([JobKind.standard])

    reopened = Manager(serverless=True, license_key=license_key, workdir=workdir)
    jobs = reopened.get_jobs_by_name("iris_serverless")
    assert jobs
    assert jobs[0].status == "finished"


def test_multi_table(manager: Manager) -> None:
    patient = pd.read_csv(FIXTURES / "patient.csv")
    visit = pd.read_csv(FIXTURES / "visit.csv")

    runner = manager.create_runner("multi_serverless")
    runner.add_table("patient", data=patient, primary_key="p_id")
    runner.add_table("visit", data=visit, primary_key="visit_id", foreign_keys=["patient_id"])
    runner.add_link("patient", "p_id", "visit", "patient_id")
    runner.set_parameters("patient", k=5, ncp=2)
    runner.set_parameters("visit", k=5, ncp=2)
    runner.run([JobKind.standard])

    assert runner.get_status(JobKind.standard) == "finished"
    assert runner.shuffled("patient").shape[0] == patient.shape[0]
    assert runner.shuffled("visit").shape[0] == visit.shape[0]


# The renderer built in this repository, or one on PATH. The engine wheel bundles its
# own; here, with the engine installed from source, the test brings it explicitly.
BUILT_REPORT_GENERATOR = (
    Path(__file__).resolve().parents[4]
    / "reportgenerator"
    / "target"
    / "release"
    / "reportgenerator"
)
REPORT_GENERATOR = (
    str(BUILT_REPORT_GENERATOR)
    if BUILT_REPORT_GENERATOR.is_file()
    else shutil.which("reportgenerator")
)


@pytest.mark.skipif(
    REPORT_GENERATOR is None,
    reason="needs the reportgenerator binary (just build in services/reportgenerator)",
)
def test_reports_render_to_real_documents(
    tmp_path: Path, iris: pd.DataFrame, license_key: str
) -> None:
    """A report job reports `finished` even when rendering failed -- the engine then
    returns the Typst source instead of a PDF. So the check is on the bytes.
    """
    settings = ServerlessConfig(
        workdir=tmp_path / "wd", license_key=license_key, pdf_generator_binary=REPORT_GENERATOR
    )
    runner = Manager(serverless=True, serverless_config=settings).create_runner("iris_report")
    runner.add_table("iris", data=iris)
    runner.set_parameters("iris", k=5, ncp=2)
    runner.run()

    assert runner.get_status(JobKind.report) == "finished"
    # One run renders both: the basic report is a PDF, and the PIA report a Word
    # document by design (avatar_yaml forces docx for it), from the same binary.
    for report_type, suffix in ((ReportType.BASIC, "pdf"), (ReportType.PIA, "docx")):
        output = tmp_path / f"report-{report_type.value}.{suffix}"
        runner.download_report(str(output), report_type=report_type)
        content = output.read_bytes()
        if report_type is ReportType.PIA:
            with zipfile.ZipFile(io.BytesIO(content)) as docx:
                assert "word/document.xml" in docx.namelist(), docx.namelist()[:10]
        else:
            assert content.startswith(b"%PDF-"), f"not a PDF, starts with {content[:40]!r}"
        assert len(content) > 20_000, f"suspiciously small {suffix}: {len(content)} bytes"


class TestLicenceIsEnforcedAgainstTheRealEngine:
    """The licence is not decoration: it decides what actually runs."""

    def test_no_licence_refuses_to_start(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty key falls back to the environment and the home licence file; neither
        # may answer for this test on a machine that has one.
        monkeypatch.delenv("AVATAR_LICENSE_KEY", raising=False)
        monkeypatch.setattr(
            "avatars.serverless.config.HOME_LICENSE_PATH", tmp_path / "no-licence.key"
        )
        with pytest.raises(LicenseError, match="AVTR-LIC-001"):
            Manager(serverless=True, license_key="", workdir=tmp_path / "wd")

    def test_a_tampered_licence_refuses_to_start(self, tmp_path: Path, license_key: str) -> None:
        header, payload, signature = license_key.split(".")
        forged = f"{header}.{payload[:-4]}AAAA.{signature}"
        with pytest.raises(LicenseError, match="AVTR-LIC-002"):
            Manager(serverless=True, license_key=forged, workdir=tmp_path / "wd")

    def test_an_expired_licence_refuses_to_start(
        self, tmp_path: Path, make_license: Callable[..., str]
    ) -> None:
        expired = make_license(expires_in=timedelta(days=-1))
        with pytest.raises(LicenseError, match="AVTR-LIC-003"):
            Manager(serverless=True, license_key=expired, workdir=tmp_path / "wd")

    def test_a_process_runs_under_one_licence(
        self, tmp_path: Path, make_license: Callable[..., str]
    ) -> None:
        """The first licence stays in force: the same one again is fine, another is not."""
        first = make_license(max_lines=10)
        Manager(serverless=True, license_key=first, workdir=tmp_path / "a")

        Manager(serverless=True, license_key=first, workdir=tmp_path / "b")
        with pytest.raises(LicenseError, match="AVTR-LIC-007"):
            Manager(serverless=True, license_key=make_license(), workdir=tmp_path / "c")

    def test_jobs_run_in_parallel_under_the_licence_in_force(
        self,
        tmp_path: Path,
        iris: pd.DataFrame,
        make_license: Callable[..., str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two jobs on two threads overlap, and each enforces the licence's row cap."""
        from avatar.processing import avatarize  # noqa: PLC0415

        key = make_license(max_lines=10)
        real_process = avatarize.process
        # Each job waits here for the other: both are inside the engine at once, or the
        # barrier times out and both jobs fail with something other than the row cap.
        both_running = threading.Barrier(2, timeout=30)

        def process_when_both_run(*args: Any, **kwargs: Any) -> None:
            both_running.wait()
            real_process(*args, **kwargs)

        monkeypatch.setattr(avatarize, "process", process_when_both_run)
        runners = []
        for name in ("a", "b"):
            runner = Manager(
                serverless=True, license_key=key, workdir=tmp_path / name
            ).create_runner(f"parallel_{name}")
            runner.add_table("iris", data=iris)
            runner.set_parameters("iris", k=5, ncp=2)
            runners.append(runner)

        threads = [
            threading.Thread(target=runner.run, args=([JobKind.standard],)) for runner in runners
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for runner in runners:
            assert runner.get_status(JobKind.standard) == "error"
            assert "too large" in runner.get_job(JobKind.standard).exception

    def test_a_row_cap_stops_an_oversized_dataset(
        self, tmp_path: Path, iris: pd.DataFrame, make_license: Callable[..., str]
    ) -> None:
        """The cap is enforced by the engine, from the licence, mid-run."""
        capped = make_license(max_lines=10)
        runner = Manager(
            serverless=True, license_key=capped, workdir=tmp_path / "wd"
        ).create_runner("too_big")
        runner.add_table("iris", data=iris)
        runner.set_parameters("iris", k=5, ncp=2)
        runner.run([JobKind.standard])

        assert runner.get_status(JobKind.standard) == "error"
        assert "too large for your current license" in runner.get_job(JobKind.standard).exception

    def test_a_missing_feature_scope_stops_the_job(
        self, tmp_path: Path, iris: pd.DataFrame, make_license: Callable[..., str]
    ) -> None:
        """`Config.check_perm` at the top of `process()` is the choke point."""
        narrow = make_license(feature_scopes=[FeatureScope.SINGLE_TABLE])
        runner = Manager(
            serverless=True, license_key=narrow, workdir=tmp_path / "wd"
        ).create_runner("unlicensed_feature")
        runner.add_table("iris", data=iris)
        runner.set_parameters("iris", k=5, ncp=2)
        runner.run([JobKind.standard])

        assert runner.get_status(JobKind.standard) == "error"
        assert "license does not allow" in runner.get_job(JobKind.standard).exception
