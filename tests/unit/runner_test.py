import re
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from avatar_yaml.models.parameters import (
    AlignmentMethod,
    AugmentationStrategy,
    ExcludeVariablesMethod,
    ImputeMethod,
    ProjectionType,
    ReportLanguage,
    ReportType,
)
from avatar_yaml.models.schema import ColumnType

from avatars.constants import Results
from avatars.manager import Manager
from avatars.models import BulkDeleteResponse, JobKind
from tests.unit.conftest import FakeApiClient, JobResponseFactory, create_fake_job

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures"


class TestRunner:
    manager: Manager
    df1 = pd.DataFrame({"col1": [1, 2, 3, 4, 5], "col2": [3, 4, 5, 6, 7]})
    df_parent = pd.DataFrame({"id": [1, 2], "col2": [3, 4]})
    df_child = pd.DataFrame(
        {"id": [1, 2, 3], "id2": [1, 2, 1], "val": [5, 6, 7], "col2": [3, 4, 5]}
    )

    @classmethod
    def setup_class(cls):
        cls.manager = Manager(api_client=FakeApiClient())

    def setup_method(self):
        """Create a fresh runner for each test method."""
        self.runner = self.manager.create_runner("test")

    def test_create_runner_add_metadata_and_annotations(self):
        self.runner.add_annotations({"key": "value"})
        assert self.runner.config.avatar_metadata.spec.display_name == "test"
        assert self.runner.config.avatar_metadata.annotations["key"] == "value"

    def test_create_runner_add_versions_to_metadata(self):
        versions = self.runner.config.avatar_metadata.annotations
        assert list(versions.keys()) == ["client_type", "client_version"]
        assert versions["client_type"] == "python"
        assert versions["client_version"]
        # Assert simple semver format: major.minor.patch (e.g., 1.2.3)
        assert re.match(r"^\d+\.\d+\.\d+$", versions["client_version"])

    def test_add_annotation_do_not_overwrite_versions(self):
        self.runner.add_annotations({"key": "value"})
        versions = self.runner.config.avatar_metadata.annotations
        assert list(versions.keys()) == [
            "client_type",
            "client_version",
            "key",
        ]
        assert versions["client_type"] == "python"
        assert versions["client_version"]
        assert versions["key"] == "value"

    def test_add_table_df(self):
        self.runner.add_table("test_table", data=self.df1)
        assert "test_table" in self.runner.config.tables.keys()

    def test_add_table_from_file(self):
        self.runner.add_table("test_table", data="../fixtures/iris.csv")
        assert "test_table" in self.runner.config.tables.keys()

    def test_add_table_with_avatar(self):
        self.runner.add_table(
            "test_table", data=f"{FIXTURES_PATH}/iris.csv", avatar_data=f"{FIXTURES_PATH}/iris.csv"
        )
        assert "test_table" in self.runner.config.tables.keys()
        assert "test_table" in self.runner.config.avatar_tables.keys()

    def test_run_raises_error_when_no_avatar_table(self):
        self.runner.add_table("test_table", data=self.df1)
        self.runner.set_parameters("test_table", ncp=2)  # no avatarization parameters
        with pytest.raises(
            ValueError, match="Expected Avatar tables to be set to run signal/privacy metrics"
        ):
            self.runner.run(jobs_to_run=[JobKind.privacy_metrics])

    def test_run_metrics_with_avatar_table(self):
        self.runner.add_table("test_table", data=self.df1, avatar_data=self.df1)
        self.runner.set_parameters("test_table", ncp=2)
        self.runner.run(jobs_to_run=[JobKind.privacy_metrics, JobKind.signal_metrics])
        assert self.runner.jobs.get_launched_jobs() == [
            JobKind.signal_metrics.value,
            JobKind.privacy_metrics.value,
        ]

    def test_add_link(self):
        runner = self.manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id")
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.add_link("parent", "id", "child", "id2")
        assert len(runner.config.tables.keys()) == 2
        assert len(runner.config.tables["parent"].links) == 1

    def test_set_parameters(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2)
        assert len(runner.config.avatarization.keys()) == 1
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1

    def test_set_parameters_without_avat(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", ncp=2)
        runner.get_yaml()
        assert len(runner.config.avatarization.keys()) == 0
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1

    def test_set_parameters_with_dp(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", open_dp_epsilon=3, ncp=2)
        assert len(runner.config.avatarization.keys()) == 0
        avatarization_open_dp = getattr(runner.config, "avatarization_open_dp", None)
        assert avatarization_open_dp is not None
        assert len(avatarization_open_dp.keys()) == 1
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1

    def test_set_parameters_dp_overwrite_avatarization(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2)
        runner.set_parameters("test_table", open_dp_epsilon=3, ncp=2)
        assert runner.config.avatarization.get("test_table") is None
        avatarization_open_dp = getattr(runner.config, "avatarization_open_dp", None)
        assert avatarization_open_dp is not None
        assert avatarization_open_dp["test_table"] is not None
        assert avatarization_open_dp["test_table"].epsilon == 3
        assert avatarization_open_dp["test_table"].ncp == 2
        assert runner.config.privacy_metrics["test_table"].ncp == 2
        assert runner.config.signal_metrics["test_table"].ncp == 2

    def test_set_parameters_data_augmentation(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            k=3,
            ncp=2,
            data_augmentation_strategy=AugmentationStrategy.minority,
            data_augmentation_target_column="col2",
            data_augmentation_should_anonymize_original_table=False,
        )
        assert len(runner.config.avatarization.keys()) == 1
        augmentation_params = runner.config.avatarization["test_table"].data_augmentation
        assert augmentation_params is not None
        assert augmentation_params.augmentation_strategy == AugmentationStrategy.minority
        assert augmentation_params.target_column == "col2"
        assert augmentation_params.should_anonymize_original_table is False

    def test_set_parameters_empty(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table")
        assert len(runner.config.avatarization.keys()) == 0
        avatarization_open_dp = getattr(runner.config, "avatarization_open_dp", None)
        if avatarization_open_dp is not None:
            assert len(avatarization_open_dp.keys()) == 0
        avatarization_fast_dp = getattr(runner.config, "avatarization_fast_dp", None)
        if avatarization_fast_dp is not None:
            assert len(avatarization_fast_dp.keys()) == 0
        assert len(runner.config.privacy_metrics.keys()) == 0
        assert len(runner.config.signal_metrics.keys()) == 0

    def test_advise_parameters(self):
        manager = Manager(api_client=FakeApiClient(tables=["test"]))
        runner = manager.create_runner("test")
        runner.add_table("test", data=self.df1)
        runner.advise_parameters("test")
        assert len(runner.config.advice.keys()) == 1
        assert runner.config.avatarization["test"].k is not None

    def test_advise_parameters_multitable(self):
        manager = Manager(api_client=FakeApiClient(tables=["parent", "child"]))
        runner = manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id", individual_level=True)
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.add_link("parent", "id", "child", "id2")
        runner.advise_parameters()
        assert runner.config.avatarization["child"].k is not None
        assert runner.config.avatarization["parent"].k is not None

    def test_run(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()
        assert list(runner.jobs.get_launched_jobs()) == [
            JobKind.standard.value,
            JobKind.signal_metrics.value,
            JobKind.privacy_metrics.value,
            JobKind.report.value,
            JobKind.report.value + "_pia",
        ]

    def test_run_uses_default_report_language_for_reports(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()

        yaml = runner.get_yaml()
        assert yaml.count("language: en") == 2
        assert runner.report_language == ReportLanguage.EN

    def test_run_uses_custom_report_language_for_reports(self):
        runner = self.manager.create_runner("test", report_language=ReportLanguage.FR)
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()

        yaml = runner.get_yaml()
        assert yaml.count("language: fr") == 2
        assert runner.report_language == ReportLanguage.FR

    def test_run_does_not_recreate_report_configs_when_already_set(self):
        """When a runner is loaded from an existing config (e.g. from_yaml) with
        both report types already set, run() must not overwrite them."""
        runner = self.manager.create_runner("test", report_language=ReportLanguage.EN)
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        # Pre-populate both report configs with FR, simulating a from_yaml scenario
        runner.config.create_report(language=ReportLanguage.FR)
        runner.config.create_report(ReportType.PIA, language=ReportLanguage.FR)
        runner.run()

        assert runner.config.report[ReportType.BASIC][1] == ReportLanguage.FR
        assert runner.config.report[ReportType.PIA][1] == ReportLanguage.FR

    def test_run_creates_missing_pia_when_basic_already_set(self):
        """When BASIC report is pre-set but PIA is missing, run() creates only PIA."""
        runner = self.manager.create_runner("test", report_language=ReportLanguage.EN)
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        # Pre-populate only BASIC with FR
        runner.config.create_report(language=ReportLanguage.FR)
        runner.run()

        assert runner.config.report[ReportType.BASIC][1] == ReportLanguage.FR
        assert ReportType.PIA in runner.config.report
        assert runner.config.report[ReportType.PIA][1] == ReportLanguage.EN

    def test_run_creates_missing_basic_when_pia_already_set(self):
        """When PIA report is pre-set but BASIC is missing, run() creates only BASIC."""
        runner = self.manager.create_runner("test", report_language=ReportLanguage.EN)
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        # Pre-populate only PIA with FR
        runner.config.create_report(ReportType.PIA, language=ReportLanguage.FR)
        runner.run()

        assert ReportType.BASIC in runner.config.report
        assert runner.config.report[ReportType.BASIC][1] == ReportLanguage.EN
        assert runner.config.report[ReportType.PIA][1] == ReportLanguage.FR

    def test_run_order(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run([JobKind.signal_metrics, JobKind.privacy_metrics, JobKind.standard])
        # test the order of job creation
        assert list(runner.jobs.get_launched_jobs()) == [
            JobKind.standard.value,
            JobKind.signal_metrics.value,
            JobKind.privacy_metrics.value,
        ]

    def test_multitable(self):
        runner = self.manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id", individual_level=True)
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.set_parameters("parent", k=1)
        runner.set_parameters("child", k=1)
        runner.add_link("parent", "id", "child", "id2")
        runner.run()
        assert list(runner.config.tables.keys()) == ["parent", "child"]
        assert len(runner.config.tables["parent"].links) == 1
        assert list(runner.jobs.get_launched_jobs()) == [
            JobKind.standard.value,
            JobKind.signal_metrics.value,
            JobKind.privacy_metrics.value,
            JobKind.report.value,
            JobKind.report.value + "_pia",
        ]

    def test_get_all_results(self):
        manager = Manager(api_client=FakeApiClient(tables=["parent"]))
        runner = manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id", individual_level=True)
        runner.set_parameters("parent", k=1)
        runner.run()
        runner.get_all_results()

        assert len(runner.jobs.get_launched_jobs()) == 5
        assert list(runner.jobs.get_launched_jobs()) == [
            JobKind.standard.value,
            JobKind.signal_metrics.value,
            JobKind.privacy_metrics.value,
            JobKind.report.value,
            JobKind.report.value + "_pia",
        ]

        assert runner.results.shuffled != {}
        assert runner.results.sensitive_unshuffled != {}
        assert runner.results.privacy_metrics != {}
        assert runner.results.signal_metrics != {}
        assert runner.results.original_projections != {}
        assert runner.results.avatars_projections != {}
        assert runner.results.figures != {}

    def test_get_all_results_multitable(self):
        manager = Manager(api_client=FakeApiClient(tables=["parent", "child"]))
        runner = manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id", individual_level=True)
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.advise_parameters()
        runner.add_link("parent", "id", "child", "id2")
        runner.run()
        runner.get_all_results()

        assert list(runner.jobs.get_launched_jobs()) == [
            JobKind.advice.value + "_parameters",
            JobKind.standard.value,
            JobKind.signal_metrics.value,
            JobKind.privacy_metrics.value,
            JobKind.report.value,
            JobKind.report.value + "_pia",
        ]

        assert runner.results.shuffled.keys() == {"parent", "child"}
        assert runner.results.sensitive_unshuffled != {}
        assert runner.results.privacy_metrics != {}
        assert runner.results.signal_metrics != {}
        assert runner.results.original_projections != {}
        assert runner.results.avatars_projections != {}
        assert runner.results.figures != {}

    def test_from_yaml(self):
        runner = self.manager.create_runner("test")
        runner.from_yaml(f"{FIXTURES_PATH}/yaml_from_web.yaml")
        assert len(runner.config.tables.keys()) == 1
        assert len(runner.config.avatarization.keys()) == 1
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1
        iris_params = runner.config.avatarization["iris"]
        assert iris_params.k == 30
        assert iris_params.ncp == 4
        assert iris_params.use_categorical_reduction is True
        assert iris_params.imputation is not None
        assert iris_params.imputation["method"] == "mean"
        assert iris_params.exclude_variables is not None
        assert iris_params.exclude_variables["variable_names"] == ["variety"]
        assert iris_params.exclude_variables["replacement_strategy"] == "coordinate_similarity"

    def test_report_raises_error(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test", data=self.df1)
        runner.set_parameters("test", k=3)
        with pytest.raises(
            ValueError,
            match="Expected Privacy and Signal jobs to be created before running report",
        ):
            runner.run(jobs_to_run=[JobKind.report])

    def test_delete_table(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test", data=self.df1)
        runner.delete_table("test")
        assert "test" not in runner.config.tables.keys()

    def test_delete_link(self):
        runner = self.manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id")
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.add_link("parent", "id", "child", "id2")
        assert len(runner.config.tables["parent"].links) == 1
        runner.delete_link("parent", "child")
        assert len(runner.config.tables["parent"].links) == 0

    def test_delete_parameters(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2, use_categorical_reduction=True)
        assert runner.config.avatarization["test_table"].k == 3
        assert runner.config.avatarization["test_table"].ncp == 2
        assert runner.config.avatarization["test_table"].use_categorical_reduction
        assert runner.config.privacy_metrics["test_table"].ncp == 2
        assert runner.config.privacy_metrics["test_table"].use_categorical_reduction
        assert runner.config.signal_metrics["test_table"].ncp == 2
        assert runner.config.signal_metrics["test_table"].use_categorical_reduction

        runner.delete_parameters("test_table")
        assert len(runner.config.avatarization.keys()) == 0
        assert len(runner.config.privacy_metrics.keys()) == 0
        assert len(runner.config.signal_metrics.keys()) == 0

    def test_add_table_change_dtype(self):
        runner = self.manager.create_runner("test")
        runner.add_table(
            "test_table",
            data=self.df1,
            types={"col1": ColumnType.CATEGORY, "col2": ColumnType.CATEGORY},
        )
        assert runner.config.tables["test_table"].columns[0].type == ColumnType.CATEGORY
        assert runner.config.tables["test_table"].columns[1].type == ColumnType.CATEGORY

    def test_add_table_change_dtype_with_pandas(self):
        runner = self.manager.create_runner("test")
        df = self.df1
        df["col1"] = df["col1"].astype("object")
        df["col2"] = df["col2"].astype("object")
        runner.add_table(
            "test_table",
            data=self.df1,
        )
        assert runner.config.tables["test_table"].columns[0].type == ColumnType.CATEGORY
        assert runner.config.tables["test_table"].columns[1].type == ColumnType.CATEGORY

    def test_update_parameters_basic(self):
        """Test updating basic parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        # Set initial parameters
        runner.set_parameters("test_table", k=3, ncp=2, use_categorical_reduction=False)

        # Update only k parameter
        runner.update_parameters("test_table", k=5)

        # Verify that k was updated and other parameters remained unchanged
        assert runner.config.avatarization["test_table"].k == 5
        assert runner.config.avatarization["test_table"].ncp == 2
        assert not runner.config.avatarization["test_table"].use_categorical_reduction

    def test_update_parameters_without_set(self):
        """Test that updating parameters without setting them first raises an error."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)

        with pytest.raises(ValueError) as excinfo:
            runner.update_parameters("test_table", k=5)
            assert (
                str(excinfo.value) == "No existing parameters found for table 'test_table'. "
                "Use set_parameters to create new parameters."
            )

    def test_update_parameters_from_standard_to_dp(self):
        """Test updating from standard avatarization to DP avatarization."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        # Set initial parameters with standard avatarization
        runner.set_parameters("test_table", k=3, ncp=2)

        # Update to use DP instead of k
        runner.update_parameters("test_table", open_dp_epsilon=0.5, k=None)

        # Verify that we switched from standard to DP avatarization
        assert "test_table" not in runner.config.avatarization
        avatarization_open_dp = getattr(runner.config, "avatarization_open_dp", None)
        assert avatarization_open_dp is not None
        assert "test_table" in avatarization_open_dp
        assert avatarization_open_dp["test_table"].epsilon == 0.5
        assert avatarization_open_dp["test_table"].ncp == 2  # Should preserve other params

    def test_update_parameters_add_exclude_variables(self):
        """Test adding exclude variables to existing parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        # Set initial parameters
        runner.set_parameters("test_table", k=3)

        # Update to add exclude variables
        exclude_vars = ["col1"]
        runner.update_parameters(
            "test_table",
            exclude_variable_names=exclude_vars,
            exclude_variable_method=ExcludeVariablesMethod.ROW_ORDER,
        )

        # Verify exclude variables were added
        assert (
            runner.config.avatarization["test_table"].exclude_variables["variable_names"]
            == exclude_vars
        )
        assert (
            runner.config.avatarization["test_table"].exclude_variables["replacement_strategy"]
            == "row_order"
        )
        assert runner.config.avatarization["test_table"].k == 3  # Original parameter preserved
        assert (
            runner.config.privacy_metrics["test_table"].exclude_variables["variable_names"]
            == exclude_vars
        )
        assert (
            runner.config.privacy_metrics["test_table"].exclude_variables["replacement_strategy"]
            == "row_order"
        )
        assert (
            runner.config.signal_metrics["test_table"].exclude_variables["variable_names"]
            == exclude_vars
        )
        assert (
            runner.config.signal_metrics["test_table"].exclude_variables["replacement_strategy"]
            == "row_order"
        )

    def test_update_parameters_with_imputation(self):
        """Test updating imputation parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        # Set initial parameters
        runner.set_parameters("test_table", k=3, imputation_method=ImputeMethod.MEDIAN)

        # Update imputation method and add k parameter
        runner.update_parameters(
            "test_table",
            imputation_method=ImputeMethod.KNN,
            imputation_k=5,
            imputation_return_data_imputed=True,
        )

        # Verify imputation parameters were updated
        assert runner.config.avatarization["test_table"].imputation["method"] == "knn"
        assert runner.config.avatarization["test_table"].imputation["k"] == 5
        assert runner.config.avatarization["test_table"].k == 3  # Original k preserved
        assert runner.config.avatarization["test_table"].imputation["return_data_imputed"] is True

    def test_update_parameters_with_time_series(self):
        """Test updating time series parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1, time_series_time="col1")
        # Set initial parameters
        runner.set_parameters(
            "test_table", k=3, time_series_nf=2, time_series_projection_type=ProjectionType.FPCA
        )

        # Update time series parameters
        runner.update_parameters(
            "test_table", time_series_method=AlignmentMethod.MEAN, time_series_nb_points=10
        )

        # Verify time series parameters were updated
        assert runner.config.time_series["test_table"].projection["nf"] == 2  # Preserved
        assert (
            runner.config.time_series["test_table"].projection["projection_type"] == "fpca"
        )  # Preserved
        assert runner.config.time_series["test_table"].alignment["method"] == "mean"  # Updated
        assert runner.config.time_series["test_table"].alignment["nb_points"] == 10  # Updated

    def test_update_parameters_with_privacy_metrics(self):
        """Test updating privacy metrics parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        # Set initial parameters
        runner.set_parameters("test_table", k=3, known_variables=["col1"])

        # Update privacy metrics parameters
        runner.update_parameters(
            "test_table",
            known_variables=["col2"],
            target="col1",
            quantile_threshold=80,
        )

        # Verify privacy metrics parameters were updated
        assert runner.config.privacy_metrics["test_table"].known_variables == ["col2"]
        assert runner.config.privacy_metrics["test_table"].target == "col1"
        assert runner.config.privacy_metrics["test_table"].quantile_threshold == 80
        assert runner.config.avatarization["test_table"].k == 3  # Original k preserved

    def test_extract_current_parameters_standard_avatarization_pipeline(self):
        """Test extracting parameters with standard avatarization."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            k=3,
            ncp=2,
            use_categorical_reduction=True,
            column_weights={"col1": 0.7, "col2": 0.3},
            exclude_variable_names=["col2"],
            exclude_variable_method=ExcludeVariablesMethod.COORDINATE_SIMILARITY,
            imputation_method=ImputeMethod.KNN,
            imputation_k=5,
            imputation_training_fraction=0.8,
            imputation_return_data_imputed=True,
            known_variables=["col1"],
            target="col2",
        )

        # Extract parameters
        current_params = runner._extract_current_parameters("test_table")

        # Verify extracted parameters match what was set
        assert current_params["k"] == 3
        assert current_params["ncp"] == 2
        assert current_params["use_categorical_reduction"]
        assert current_params["column_weights"] == {"col1": 0.7, "col2": 0.3}
        assert current_params["exclude_variable_names"] == ["col2"]
        assert (
            current_params["exclude_replacement_strategy"]
            == ExcludeVariablesMethod.COORDINATE_SIMILARITY
        )
        assert current_params["imputation_method"] == ImputeMethod.KNN
        assert current_params["imputation_k"] == 5
        assert current_params["imputation_training_fraction"] == 0.8
        assert current_params["imputation_return_data_imputed"] is True
        assert current_params["known_variables"] == ["col1"]
        assert current_params["target"] == "col2"

        privacy_params = runner.config.privacy_metrics["test_table"]
        signal_params = runner.config.signal_metrics["test_table"]

        assert privacy_params.ncp == 2
        assert privacy_params.use_categorical_reduction is True
        assert privacy_params.column_weights == {"col1": 0.7, "col2": 0.3}
        assert privacy_params.known_variables == ["col1"]
        assert privacy_params.exclude_variables["variable_names"] == ["col2"]
        assert (
            privacy_params.exclude_variables["replacement_strategy"]
            == ExcludeVariablesMethod.COORDINATE_SIMILARITY
        )
        assert signal_params.ncp == 2
        assert signal_params.use_categorical_reduction is True
        assert signal_params.column_weights == {"col1": 0.7, "col2": 0.3}
        assert signal_params.exclude_variables["variable_names"] == ["col2"]
        assert (
            signal_params.exclude_variables["replacement_strategy"]
            == ExcludeVariablesMethod.COORDINATE_SIMILARITY
        )

    def test_extract_current_parameters_open_dp_avatarization(self):
        """Test extracting parameters with OpenDP avatarization."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            open_dp_epsilon=0.5,
            ncp=2,
            use_categorical_reduction=True,
        )

        # Extract parameters
        current_params = runner._extract_current_parameters("test_table")

        # Verify extracted parameters match what was set
        assert current_params["open_dp_epsilon"] == 0.5
        assert current_params["ncp"] == 2
        assert current_params["use_categorical_reduction"]
        assert "k" not in current_params

    def test_extract_current_parameters_time_series(self):
        """Test extracting parameters with time series configuration."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1, time_series_time="col1")
        runner.set_parameters(
            "test_table",
            k=3,
            time_series_nf=5,
            time_series_projection_type=ProjectionType.FPCA,
            time_series_nb_points=10,
            time_series_method=AlignmentMethod.MAX,
        )

        # Extract parameters
        current_params = runner._extract_current_parameters("test_table")

        # Verify time series parameters are extracted correctly
        assert current_params["time_series_nf"] == 5
        assert current_params["time_series_projection_type"] == ProjectionType.FPCA
        assert current_params["time_series_nb_points"] == 10
        assert current_params["time_series_method"] == AlignmentMethod.MAX

    def test_get_not_created_job(self):
        """Test getting a job that was not created."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run(jobs_to_run=[JobKind.standard])
        with pytest.raises(
            ValueError, match=f"Expected job '{JobKind.privacy_metrics.value}' to be created"
        ):
            runner.get_status(JobKind.privacy_metrics)

    def test_get_failed_job(self):
        """Test getting a job that failed."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()
        # Return a failed job response
        runner.client.jobs.get_job_status = lambda job_id: JobResponseFactory().build(
            name="name",
            set_name=uuid4(),
            parameters_name="parameters_name",
            created_at="2023-10-01T00:00:00Z",
            kind=JobKind.standard,
            status="error",
            exception="Job is not valid",
            done=True,
            progress=1.0,
        )
        with pytest.raises(
            ValueError,
            match=f"""Job {JobKind.standard.value} failed with exception:""",
        ):
            runner.get_all_results()

    def test_get_results_on_invalid_table(self):
        """Test getting results that do not exist."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()
        with pytest.raises(ValueError, match="Expected table 'NOT_VALID' to be created."):
            runner.get_specific_result(
                table_name="NOT_VALID", job_name=JobKind.standard, result=Results.SHUFFLED
            )

    def test_run_without_avatarization_parameters(self):
        """Test runner when avatarization parameters were not set."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", ncp=15)
        with pytest.raises(
            ValueError,
            match="Expected k or epsilon to be set to run an avatarization job,",
        ):
            runner.run()

    def test_run_without_any_parameters(self):
        """Test runner when no parameters were set."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        with pytest.raises(
            ValueError,
            match="Expected k or epsilon to be set to run an avatarization job,",
        ):
            runner.run()

    def test_run_twice_emits_warning_with_and_clears_jobs(self):
        """Re-running a runner that already has results emits a UserWarning with the set_name."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()
        old_set_name = runner.set_name

        with pytest.warns(UserWarning, match=old_set_name):
            runner.run()

        assert runner.set_name != old_set_name
        assert len(runner.results_urls) == 0 or all(
            runner.set_name in str(v) for v in runner.results_urls.values()
        )

    def test_populate_existing_jobs_reraises_non_results_404(self):
        """A 404 that is not the results-file-missing error must be re-raised."""
        set_name = uuid4()
        fake_client = FakeApiClient()
        fake_client.jobs.add_job(
            create_fake_job(
                name="job-standard",
                set_name=set_name,
                kind=JobKind.standard,
                parameters_name=JobKind.standard.value,
                done=True,
                exception="",
            )
        )

        manager = Manager(api_client=fake_client)
        runner = manager.create_runner("test")
        runner.set_name = str(set_name)

        fake_client.results.get_results = lambda _: (_ for _ in ()).throw(
            Exception(
                "Got error in HTTP request: get /results/job-standard. "
                "Error status 404 - Job 'job-standard' either does not exist or you do not "
                "have access to it"
            )
        )

        with pytest.raises(Exception, match="Error status 404"):
            runner._populate_results_from_existing_jobs()

    def test_print_parameters_invalid_table(self):
        """Test printing parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2, use_categorical_reduction=True)
        with pytest.raises(ValueError, match="Expected table 'NOT_VALID' to be created."):
            runner.print_parameters("NOT_VALID")

    def test_print_parameters_every_table(self):
        """Test printing parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2, use_categorical_reduction=True)
        runner.print_parameters()

    @pytest.mark.parametrize(
        "max_distribution_plots",
        [
            pytest.param(50, id="custom"),
            pytest.param(-1, id="no_limit"),
            pytest.param(0, id="zero"),
        ],
    )
    def test_runner_init_max_distribution_plots(self, max_distribution_plots: int):
        """Test configuring max_distribution_plots when creating the runner."""
        runner = self.manager.create_runner("test", max_distribution_plots=max_distribution_plots)
        assert runner.config.max_distribution_plots == max_distribution_plots

    def test_max_distribution_plots_in_yaml(self):
        """Test that max_distribution_plots appears in generated YAML."""
        runner = self.manager.create_runner("test", max_distribution_plots=50)
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        yaml = runner.get_yaml()
        assert "max_distribution_plots: 50" in yaml

    def test_set_parameters_with_fast_dp_epsilon(self):
        """Test setting FastDP parameters via Runner.set_parameters()."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            fast_dp_epsilon=1.5,
        )

        # Should create avatarization_fast_dp, not standard avatarization
        assert len(runner.config.avatarization.keys()) == 0
        assert len(runner.config.avatarization_open_dp.keys()) == 0
        assert "test_table" in runner.config.avatarization_fast_dp

        # Verify parameter values (only epsilon is exposed)
        params = runner.config.avatarization_fast_dp["test_table"]
        assert params.epsilon == 1.5
        # Mechanism defaults to "gaussian" when not specified
        assert params.mechanism == "gaussian"

    def test_extract_current_parameters_fast_dp(self):
        """Test Runner._extract_current_parameters for FastDP."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            fast_dp_epsilon=1.5,
            ncp=2,
            use_categorical_reduction=True,
        )

        current_params = runner._extract_current_parameters("test_table")

        # Only epsilon and common params are exposed/extracted
        assert current_params["fast_dp_epsilon"] == 1.5
        assert current_params["ncp"] == 2
        assert current_params["use_categorical_reduction"]

        # Mechanism-specific parameters are not exposed
        assert "fast_dp_mechanism" not in current_params
        assert "fast_dp_gmm_n_components" not in current_params

    def test_update_parameters_with_fast_dp(self):
        """Test Runner.update_parameters() with FastDP parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            fast_dp_epsilon=1.0,
            ncp=2,
        )

        # Update only epsilon
        runner.update_parameters("test_table", fast_dp_epsilon=2.0)

        params = runner.config.avatarization_fast_dp["test_table"]
        assert params.epsilon == 2.0  # Updated
        assert params.ncp == 2  # Preserved

    def test_cannot_mix_k_and_fast_dp_epsilon(self):
        """Test that setting both k and fast_dp_epsilon raises an error."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)

        with pytest.raises(ValueError, match="Expected either k or fast_dp_epsilon"):
            runner.set_parameters(
                "test_table",
                k=5,
                fast_dp_epsilon=1.5,
            )

    def test_fast_dp_overwrites_standard_avatarization(self):
        """Test that FastDP parameters overwrite standard avatarization."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)

        # Set standard parameters first
        runner.set_parameters("test_table", k=5, ncp=2)
        assert "test_table" in runner.config.avatarization

        # Switch to FastDP
        runner.set_parameters("test_table", fast_dp_epsilon=1.5)

        # Standard avatarization should be cleared
        assert runner.config.avatarization.get("test_table") is None
        assert "test_table" in runner.config.avatarization_fast_dp
        assert runner.config.avatarization_fast_dp["test_table"].epsilon == 1.5

    def test_delete_single_job(self):
        """Test that delete with a single JobKind returns a BulkDeleteResponse."""
        self.runner.add_table("test_table", data=self.df1, avatar_data=self.df1)
        self.runner.set_parameters("test_table", k=5)
        self.runner.run(jobs_to_run=[JobKind.standard])

        result = self.runner.delete(JobKind.standard)

        assert isinstance(result, BulkDeleteResponse)
        assert len(result.deleted_jobs) == 1
        assert result.failed_jobs == []

    def test_delete_list_of_jobs(self):
        """Test that delete with a list of JobKinds returns a BulkDeleteResponse."""
        self.runner.add_table("test_table", data=self.df1, avatar_data=self.df1)
        self.runner.set_parameters("test_table", k=5)
        self.runner.run(
            jobs_to_run=[JobKind.standard, JobKind.privacy_metrics, JobKind.signal_metrics]
        )

        result = self.runner.delete([JobKind.standard, JobKind.privacy_metrics])

        assert isinstance(result, BulkDeleteResponse)
        assert len(result.deleted_jobs) == 2
        assert result.failed_jobs == []

    def test_delete_raises_when_job_not_launched(self):
        """Test that delete raises ValueError when the job was never launched."""
        with pytest.raises(ValueError, match="Expected job 'standard' to be created"):
            self.runner.delete(JobKind.standard)

    def test_delete_all_jobs_no_args(self):
        """Test that delete() with no arguments deletes all launched jobs."""
        self.runner.add_table("test_table", data=self.df1, avatar_data=self.df1)
        self.runner.set_parameters("test_table", k=5)
        self.runner.run(
            jobs_to_run=[JobKind.standard, JobKind.privacy_metrics, JobKind.signal_metrics]
        )

        result = self.runner.delete()

        assert isinstance(result, BulkDeleteResponse)
        assert len(result.deleted_jobs) == 3
        assert result.failed_jobs == []

    def test_delete_no_args_when_no_jobs_launched(self):
        """Test that delete() returns empty response when no jobs were launched."""
        result = self.runner.delete()

        assert isinstance(result, BulkDeleteResponse)
        assert result.deleted_jobs == []
        assert result.failed_jobs == []
