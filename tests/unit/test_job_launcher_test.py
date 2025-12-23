"""Tests for JobLauncher class."""

from uuid import uuid4

import pytest
from avatar_yaml import Config

from avatars.job_launcher import JobLauncher
from avatars.models import JobKind
from tests.unit.conftest import FakeApiClient


class TestJobLauncher:
    """Test suite for JobLauncher class."""

    @pytest.fixture(scope="function")
    def config(self):
        """Create a fresh config with a table for each test."""
        config = Config(set_name="test_set")
        config.create_table(
            table_name="test_table",
            original_volume="volume",
            original_file="test.csv",
        )
        return config

    @pytest.fixture(scope="function")
    def launcher(self, config) -> JobLauncher:
        """Create a fresh JobLauncher instance with fake API client for each test."""
        client = FakeApiClient(tables=["test_table"])
        return JobLauncher(client=client, config=config)

    @pytest.mark.parametrize(
        "job_kind,pia_report,expected",
        [
            (JobKind.standard, False, "standard"),
            (JobKind.standard, True, "standard"),
            (JobKind.privacy_metrics, False, "privacy_metrics"),
            (JobKind.privacy_metrics, True, "privacy_metrics"),
            (JobKind.signal_metrics, False, "signal_metrics"),
            (JobKind.signal_metrics, True, "signal_metrics"),
            (JobKind.report, False, "report"),
            (JobKind.report, True, "report_pia"),
        ],
    )
    def test_get_parameters_name(self, launcher, job_kind, pia_report, expected):
        """Test get_parameters_name for different job kinds."""
        assert launcher.get_parameters_name(job_kind, pia_report=pia_report) == expected

    def test_launch_standard_job_without_parameters_raises_error(self, launcher):
        """Test that launching standard job without avatarization parameters raises error."""
        set_name = str(uuid4())
        with pytest.raises(
            ValueError,
            match="Expected k or epsilon to be set to run an avatarization job,",
        ):
            launcher.launch_job(JobKind.standard, set_name)

    def test_launch_standard_job_with_avatarization_parameters(self, launcher):
        """Test launching standard job with avatarization parameters."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)

        assert launcher.set_name == set_name
        assert "standard" in launcher.jobs.keys()
        assert launcher.has_job(JobKind.standard)

    def test_launch_standard_job_with_dp_parameters(self, launcher):
        """Test launching standard job with differential privacy parameters."""
        launcher.config.create_avatarization_dp_parameters("test_table", epsilon=1.0, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)

        assert launcher.set_name == set_name
        assert "standard" in launcher.jobs
        assert launcher.has_job(JobKind.standard)

    def test_launch_privacy_metrics_without_avatar_raises_error(self, launcher):
        """Test that privacy metrics without standard job or avatar data raises error."""
        launcher.config.get_yaml()
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        set_name = str(uuid4())

        with pytest.raises(
            ValueError,
            match="Expected Avatar tables to be set to run signal/privacy metrics",
        ):
            launcher.launch_job(JobKind.privacy_metrics, set_name)

    def test_launch_privacy_metrics_with_avatar_data(self, launcher):
        """Test launching privacy metrics with avatar data provided."""
        launcher.config.create_table(
            table_name="test_table_with_avatars",
            original_volume="volume",
            original_file="test.csv",
            avatar_volume="volume",
            avatar_file="test_avatars.csv",
        )
        launcher.config.create_privacy_metrics_parameters("test_table_with_avatars", ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.privacy_metrics, set_name)

        assert "privacy_metrics" in launcher.jobs.keys()

    def test_launch_privacy_metrics_after_standard(self, launcher):
        """Test launching privacy metrics after standard job."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        launcher.launch_job(JobKind.privacy_metrics, set_name)

        assert "standard" in launcher.jobs.keys()
        assert "privacy_metrics" in launcher.jobs.keys()

    @pytest.mark.parametrize(
        "job_kind",
        [None, JobKind.signal_metrics, JobKind.privacy_metrics],
    )
    def test_launch_report_without_metrics_raises_error(self, job_kind, launcher):
        """Test that launching report without metrics raises error."""
        set_name = str(uuid4())
        if job_kind is not None:
            launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
            launcher.launch_job(JobKind.standard, set_name)
            if job_kind == JobKind.signal_metrics:
                launcher.config.create_signal_metrics_parameters("test_table", ncp=30)
            else:
                launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
            launcher.launch_job(job_kind, set_name)

        with pytest.raises(
            ValueError,
            match="Expected Privacy and Signal jobs to be created before running report",
        ):
            launcher.launch_job(JobKind.report, set_name)

    def test_launch_report_creates_both_reports(self, launcher):
        """Test that launching report job creates both standard and PIA reports."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        launcher.config.create_signal_metrics_parameters("test_table", ncp=30)
        launcher.config.create_report()
        launcher.config.create_report(report_type="pia")
        set_name = str(uuid4())

        # Launch prerequisite jobs
        launcher.launch_job(JobKind.standard, set_name)
        launcher.launch_job(JobKind.privacy_metrics, set_name)
        launcher.launch_job(JobKind.signal_metrics, set_name)

        # Launch report job
        launcher.launch_job(JobKind.report, set_name)

        assert "report" in launcher.jobs
        assert "report_pia" in launcher.jobs
        assert launcher.has_job(JobKind.report)
        assert launcher.has_job("report_pia")

    def test_get_job_dependencies_for_standard(self, launcher):
        """Test that standard job has no dependencies."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        dependencies = launcher._get_job_dependencies(JobKind.standard)

        assert dependencies == []

    def test_get_job_dependencies_for_metrics(self, launcher):
        """Test that metrics jobs depend on standard job."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)

        privacy_dependencies = launcher._get_job_dependencies(JobKind.privacy_metrics)
        signal_dependencies = launcher._get_job_dependencies(JobKind.signal_metrics)

        assert len(privacy_dependencies) == 1
        assert len(signal_dependencies) == 1
        assert privacy_dependencies == signal_dependencies

    def test_get_job_dependencies_for_report(self, launcher):
        """Test that report job depends on both metrics jobs."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        launcher.config.create_signal_metrics_parameters("test_table", ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        launcher.launch_job(JobKind.privacy_metrics, set_name)
        launcher.launch_job(JobKind.signal_metrics, set_name)

        report_dependencies = launcher._get_job_dependencies(JobKind.report)

        assert len(report_dependencies) == 2

    def test_get_job_response_not_found_raises_error(self, launcher):
        """Test that getting non-existent job raises error."""
        with pytest.raises(ValueError, match="Expected job 'standard' to be created"):
            launcher.get_job_response(JobKind.standard)

    def test_has_job_returns_false_when_not_launched(self, launcher):
        """Test has_job returns False for non-launched jobs."""
        assert not launcher.has_job(JobKind.standard)
        assert not launcher.has_job("report_pia")

    def test_has_job_returns_true_when_launched(self, launcher):
        """Test has_job returns True for launched jobs."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)

        assert launcher.has_job(JobKind.standard)
        assert launcher.has_job("standard")

    def test_get_launched_jobs_empty_initially(self, launcher):
        """Test get_launched_jobs returns empty list initially."""
        assert launcher.get_launched_jobs() == []

    def test_get_launched_jobs_returns_all_launched(self, launcher):
        """Test get_launched_jobs returns all launched job names."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        launcher.config.create_signal_metrics_parameters("test_table", ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        launcher.launch_job(JobKind.privacy_metrics, set_name)
        launcher.launch_job(JobKind.signal_metrics, set_name)

        launched = launcher.get_launched_jobs()

        assert len(launched) == 3
        assert "standard" in launched
        assert "privacy_metrics" in launched
        assert "signal_metrics" in launched

    def test_get_launched_jobs_includes_pia_report(self, launcher):
        """Test that get_launched_jobs includes PIA report when report is launched."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        launcher.config.create_signal_metrics_parameters("test_table", ncp=30)
        launcher.config.create_report()
        launcher.config.create_report(report_type="pia")
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        launcher.launch_job(JobKind.privacy_metrics, set_name)
        launcher.launch_job(JobKind.signal_metrics, set_name)
        launcher.launch_job(JobKind.report, set_name)

        launched = launcher.get_launched_jobs()

        assert "report" in launched
        assert "report_pia" in launched

    def test_get_job_status(self, launcher):
        """Test getting job status from API."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        status = launcher.get_job_status(JobKind.standard)

        assert status.status == "finished"
        assert status.done is True

    def test_get_job_status_by_string(self, launcher):
        """Test getting job status by string name."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        launcher.config.create_privacy_metrics_parameters("test_table", ncp=30)
        launcher.config.create_signal_metrics_parameters("test_table", ncp=30)
        launcher.config.create_report()
        launcher.config.create_report(report_type="pia")
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)
        launcher.launch_job(JobKind.privacy_metrics, set_name)
        launcher.launch_job(JobKind.signal_metrics, set_name)
        launcher.launch_job(JobKind.report, set_name)

        pia_status = launcher.get_job_status("report_pia")

        assert pia_status.status == "finished"
        assert pia_status.done is True

    def test_has_job_with_job_kind_enum(self, launcher):
        """Test has_job works with JobKind enum."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)

        # Should work with enum
        assert launcher.has_job(JobKind.standard)
        # Should also work with string
        assert launcher.has_job("standard")

    def test_get_job_response_with_job_kind_enum(self, launcher):
        """Test get_job_response works with JobKind enum."""
        launcher.config.create_avatarization_parameters("test_table", k=20, ncp=30)
        set_name = str(uuid4())

        launcher.launch_job(JobKind.standard, set_name)

        # Should work with enum
        response_enum = launcher.get_job_response(JobKind.standard)
        # Should also work with string
        response_str = launcher.get_job_response("standard")

        assert response_enum.name == response_str.name
