from pathlib import Path

import pytest

from avatars.manager import Manager
from avatars.serverless.config import (
    HOME_LICENSE_PATH,
    LICENSE_ENV_VAR,
    LICENSE_FILENAME,
    ServerlessConfig,
    new_seeding_salt,
)


@pytest.fixture(autouse=True)
def _no_prefixed_licence_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    # AVATAR_SERVERLESS_LICENSE_KEY lands in `license_key` and outranks every other
    # place, so one left in the environment would answer for the fallback tests.
    monkeypatch.delenv("AVATAR_SERVERLESS_LICENSE_KEY", raising=False)


class TestLicenceResolution:
    def test_an_explicit_key_wins(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv(LICENSE_ENV_VAR, "from-env")
        (tmp_path / LICENSE_FILENAME).write_text("from-file")
        settings = ServerlessConfig(workdir=tmp_path, license_key="explicit")
        assert settings.resolve_license_key() == "explicit"

    def test_the_environment_beats_a_file(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv(LICENSE_ENV_VAR, "from-env")
        (tmp_path / LICENSE_FILENAME).write_text("from-file")
        assert ServerlessConfig(workdir=tmp_path).resolve_license_key() == "from-env"

    def test_the_workdir_file_is_read_and_stripped(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
        (tmp_path / LICENSE_FILENAME).write_text("  from-file\n")
        assert ServerlessConfig(workdir=tmp_path).resolve_license_key() == "from-file"

    def test_nothing_anywhere_is_none_not_an_error(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
        monkeypatch.setattr(
            "avatars.serverless.config.HOME_LICENSE_PATH", tmp_path / "absent" / "license.key"
        )
        assert ServerlessConfig(workdir=tmp_path).resolve_license_key() is None

    def test_an_empty_file_does_not_count_as_a_key(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
        monkeypatch.setattr(
            "avatars.serverless.config.HOME_LICENSE_PATH", tmp_path / "absent" / "license.key"
        )
        (tmp_path / LICENSE_FILENAME).write_text("   \n")
        assert ServerlessConfig(workdir=tmp_path).resolve_license_key() is None

    def test_the_home_file_is_the_documented_default_location(self) -> None:
        assert HOME_LICENSE_PATH.name == LICENSE_FILENAME
        assert HOME_LICENSE_PATH.parent.name == ".avatar"


def test_an_unreadable_licence_file_is_reported_and_skipped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
    (tmp_path / "license.key").write_bytes(b"\xff\xfe not text")
    with pytest.warns(UserWarning, match="could not read the licence file"):
        ServerlessConfig(workdir=tmp_path).resolve_license_key()


def test_a_manager_workdir_under_the_home_marker_is_expanded(monkeypatch, tmp_path: Path) -> None:
    """`Manager(workdir="~/...")` assigns the field, which skips its validator."""
    monkeypatch.setenv("HOME", str(tmp_path))
    seen: dict[str, Path] = {}

    def capture(directory: Path) -> object:
        seen["workdir"] = directory
        raise RuntimeError("stop here")

    monkeypatch.setattr("avatars.serverless.workdir.Workdir", capture)
    with pytest.raises(RuntimeError, match="stop here"):
        Manager(serverless=True, workdir="~/wd")
    assert seen["workdir"] == tmp_path / "wd"


def test_a_workdir_under_the_home_marker_is_expanded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert ServerlessConfig(workdir=Path("~/wd")).workdir == tmp_path / "wd"


class TestSettings:
    def test_env_vars_are_prefixed_like_the_rest_of_the_sdk(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("AVATAR_SERVERLESS_EXECUTOR", "threads")
        assert ServerlessConfig(workdir=tmp_path).executor == "threads"

    def test_dask_is_not_an_option(self, tmp_path: Path, monkeypatch) -> None:
        """A local Dask cluster spawns worker processes, which is the thing
        serverless mode exists to avoid.
        """
        monkeypatch.setenv("AVATAR_SERVERLESS_EXECUTOR", "dask")
        with pytest.raises(ValueError, match="executor"):
            ServerlessConfig(workdir=tmp_path)

    def test_serial_is_the_default(self, tmp_path: Path) -> None:
        assert ServerlessConfig(workdir=tmp_path).executor == "serial"

    def test_batch_size_defaults_to_leaving_the_engine_alone(self, tmp_path: Path) -> None:
        assert ServerlessConfig(workdir=tmp_path).batch_size is None


class TestSeedingSalt:
    def test_within_the_range_the_engine_expects(self) -> None:
        assert 0 <= new_seeding_salt() < 2**31
