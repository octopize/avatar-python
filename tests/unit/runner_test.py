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
)
from avatar_yaml.models.schema import ColumnType

from avatars.constants import Results
from avatars.manager import Manager
from avatars.models import JobKind
from tests.unit.conftest import FakeApiClient, JobResponseFactory

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
        runner.set_parameters("test_table", dp_epsilon=3, ncp=2)
        assert len(runner.config.avatarization.keys()) == 0
        assert len(runner.config.avatarization_dp.keys()) == 1
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1

    def test_set_parameters_dp_overwrite_avatarization(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2)
        runner.set_parameters("test_table", dp_epsilon=3, ncp=2)
        assert runner.config.avatarization.get("test_table") is None
        assert runner.config.avatarization_dp["test_table"] is not None
        assert runner.config.avatarization_dp["test_table"].epsilon == 3
        assert runner.config.avatarization_dp["test_table"].ncp == 2
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
        assert len(runner.config.avatarization_dp.keys()) == 0
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
        runner.update_parameters("test_table", dp_epsilon=0.5, k=None)

        # Verify that we switched from standard to DP avatarization
        assert "test_table" not in runner.config.avatarization
        assert "test_table" in runner.config.avatarization_dp
        assert runner.config.avatarization_dp["test_table"].epsilon == 0.5
        assert (
            runner.config.avatarization_dp["test_table"].ncp == 2
        )  # Should preserve other params

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

    def test_extract_current_parameters_dp_avatarization(self):
        """Test extracting parameters with DP avatarization."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters(
            "test_table",
            dp_epsilon=0.5,
            dp_preprocess_budget_ratio=0.3,
            ncp=2,
            use_categorical_reduction=True,
        )

        # Extract parameters
        current_params = runner._extract_current_parameters("test_table")

        # Verify extracted parameters match what was set
        assert current_params["dp_epsilon"] == 0.5
        assert current_params["dp_preprocess_budget_ratio"] == 0.3
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

    def test_get_results_on_invalid_job(self):
        """Test getting results that do not exist."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run(jobs_to_run=[JobKind.standard])
        with pytest.raises(
            ValueError,
            match=f"""Expected job '{JobKind.privacy_metrics}' to be created. Try running it""",
        ):
            runner.get_specific_result(
                table_name="test_table",
                job_name=JobKind.privacy_metrics,
                result=Results.PRIVACY_METRICS,
            )

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
