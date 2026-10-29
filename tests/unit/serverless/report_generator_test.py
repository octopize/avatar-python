"""Which report renderer serverless uses: explicit, then bundled, then PATH.

The bundled one is found through the engine wheel's metadata, not PATH, because a
Jupyter kernel started from a virtualenv does not necessarily have that venv's
`bin/` on PATH -- and a missing renderer fails silently (reports come out as Typst
source), so getting this wrong would not announce itself.
"""

import os
import stat
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from avatars.serverless.engine import (
    BUNDLED_REPORT_GENERATOR,
    bundled_report_generator,
    resolve_report_generator,
)


class _FakeDistribution:
    def __init__(self, root: Path) -> None:
        self.root = root

    def locate_file(self, relative: str) -> Path:
        return self.root / relative


def _install_fake_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, executable: bool
) -> Path:
    binary = tmp_path / BUNDLED_REPORT_GENERATOR
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")
    mode = stat.S_IRUSR | stat.S_IWUSR | (stat.S_IXUSR if executable else 0)
    binary.chmod(mode)
    monkeypatch.setattr(
        "importlib.metadata.distribution", lambda name: _FakeDistribution(tmp_path)
    )
    return binary


def _no_engine(monkeypatch) -> None:
    def missing(name: str) -> None:
        raise PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.distribution", missing)


def test_the_bundled_renderer_is_found_through_the_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = _install_fake_engine(tmp_path, monkeypatch, executable=True)
    assert bundled_report_generator() == str(binary)


def test_a_bundled_file_that_is_not_executable_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pip dropping the executable bit would otherwise surface as a silent Typst report."""
    _install_fake_engine(tmp_path, monkeypatch, executable=False)
    assert bundled_report_generator() is None


def test_no_engine_wheel_means_no_bundled_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_engine(monkeypatch)
    assert bundled_report_generator() is None


def test_an_explicit_setting_wins_over_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_engine(tmp_path, monkeypatch, executable=True)
    assert resolve_report_generator("/opt/custom/reportgenerator") == "/opt/custom/reportgenerator"


def test_bundled_wins_over_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = _install_fake_engine(tmp_path, monkeypatch, executable=True)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/reportgenerator")
    assert resolve_report_generator(None) == str(binary)


def test_path_is_the_last_resort(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_engine(monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/reportgenerator")
    assert resolve_report_generator(None) == "/usr/local/bin/reportgenerator"


def test_nothing_anywhere_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_engine(monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert resolve_report_generator(None) is None


def test_the_resolved_path_is_actually_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = _install_fake_engine(tmp_path, monkeypatch, executable=True)
    assert os.access(resolve_report_generator(None) or "", os.X_OK)
    assert binary.exists()
