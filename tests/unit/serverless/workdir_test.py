from pathlib import Path

from avatars.serverless.workdir import Workdir


class TestWorkdir:
    def test_ensure_creates_the_directories_a_run_needs(self, tmp_path: Path) -> None:
        workdir = Workdir(tmp_path / "wd").ensure()
        assert workdir.input_dir.is_dir()
        assert workdir.sets_dir.is_dir()
        assert workdir.logs_dir.is_dir()

    def test_input_is_shared_across_sets(self, tmp_path: Path) -> None:
        """A table uploaded once must be visible to every later run.

        On the server ``StorageLocation.for_user(purpose="input")`` carries no
        set_name segment; this keeps that property.
        """
        workdir = Workdir(tmp_path / "wd").ensure()
        assert "sets" not in workdir.input_dir.parts
        assert workdir.input_dir.parent == workdir.root

    def test_results_are_per_set(self, tmp_path: Path) -> None:
        workdir = Workdir(tmp_path / "wd").ensure()
        assert workdir.results_dir("a") != workdir.results_dir("b")

    def test_urls_carry_the_file_scheme(self, tmp_path: Path) -> None:
        workdir = Workdir(tmp_path / "wd").ensure()
        assert workdir.input_url.startswith("file:///")
        assert workdir.results_url("s").startswith("file:///")

    def test_root_is_resolved_so_a_relative_workdir_still_yields_absolute_urls(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        workdir = Workdir(Path("relative")).ensure()
        assert workdir.root.is_absolute()
        assert workdir.input_url == f"file://{tmp_path.resolve() / 'relative' / 'input'}"
