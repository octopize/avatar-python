import pandas as pd
import pytest
from avatar_yaml.models.parameters import (
    AlignmentMethod,
    ExcludeVariablesMethod,
    ImputeMethod,
    ProjectionType,
)
from avatar_yaml.models.schema import ColumnType

from avatars.manager import Manager
from avatars.models import JobKind
from avatars.runner import Results
from tests.unit.conftest import FakeApiClient


class TestRunner:
    manager: Manager
    df1 = pd.DataFrame({"col1": [1, 2, 3, 4, 5], "col2": [3, 4, 5, 6, 7]})
    df_parent = pd.DataFrame({"id": [1, 2], "col2": [3, 4]})
    df_child = pd.DataFrame(
        {"id": [1, 2, 3], "id2": [1, 2, 1], "val": [5, 6, 7], "col2": [3, 4, 5]}
    )

    @classmethod
    def setup_class(cls):
        cls.manager = Manager("http://localhost:8000", FakeApiClient())

    def test_add_table_df(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        assert "test_table" in runner.config.tables.keys()

    def test_add_table_from_file(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data="../fixtures/iris.csv")
        assert "test_table" in runner.config.tables.keys()

    def test_add_table_with_avatar(self):
        runner = self.manager.create_runner("test")
        runner.add_table(
            "test_table", data="../fixtures/iris.csv", avatar_data="../fixtures/iris.csv"
        )
        assert "test_table" in runner.config.tables.keys()
        assert "test_table" in runner.config.avatar_tables.keys()

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

    def test_run(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()
        assert list(runner.jobs.keys()) == [
            JobKind.standard,
            JobKind.signal_metrics,
            JobKind.privacy_metrics,
            JobKind.report,
        ]

    def test_run_order(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run([JobKind.signal_metrics, JobKind.privacy_metrics, JobKind.standard])
        # test the order of job creation
        assert list(runner.jobs.keys()) == [
            JobKind.standard,
            JobKind.signal_metrics,
            JobKind.privacy_metrics,
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
        assert list(runner.jobs.keys()) == [
            JobKind.standard,
            JobKind.signal_metrics,
            JobKind.privacy_metrics,
            JobKind.report,
        ]

    def test_get_all_results(self):
        runner = self.manager.create_runner("test")
        runner.add_table("parent", data=self.df_parent, primary_key="id", individual_level=True)
        runner.set_parameters("parent", k=1)
        runner.run()
        runner.get_all_results()
        assert len(runner.results.keys()) == 4
        assert list(runner.results.keys()) == [
            JobKind.standard,
            JobKind.signal_metrics,
            JobKind.privacy_metrics,
            JobKind.report,
        ]
        assert len(runner.results[JobKind.standard].keys()) == 1
        for table in runner.results[JobKind.standard].keys():
            assert isinstance(
                runner.results[JobKind.standard][table][Results.SHUFFLED], pd.DataFrame
            )
            assert isinstance(
                runner.results[JobKind.standard][table][Results.UNSHUFFLED], pd.DataFrame
            )
            assert isinstance(
                runner.results[JobKind.privacy_metrics][table][Results.PRIVACY_METRICS], list
            )
            assert isinstance(
                runner.results[JobKind.signal_metrics][table][Results.SIGNAL_METRICS], list
            )

    def test_from_yaml(self):
        runner = self.manager.create_runner("test")
        runner.from_yaml("fixtures/yaml_from_web.yaml")
        assert len(runner.config.tables.keys()) == 2
        assert len(runner.config.avatarization.keys()) == 2
        assert len(runner.config.privacy_metrics.keys()) == 2
        assert len(runner.config.signal_metrics.keys()) == 2
        patient_params = runner.config.avatarization["patient"]
        assert patient_params.k == 5
        assert patient_params.ncp == 4
        assert patient_params.use_categorical_reduction == True
        assert patient_params.imputation is not None
        assert patient_params.imputation["method"] == "knn"
        assert patient_params.exclude_variables is None
        visit_params = runner.config.avatarization["visit"]
        assert visit_params.k == 5
        assert visit_params.ncp == 4
        assert visit_params.exclude_variables is not None
        assert visit_params.exclude_variables["variable_names"] == ["doctor_id"]
        assert visit_params.exclude_variables["replacement_strategy"] == "row_order"

    def test_report_raises_error(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        with pytest.raises(
            ValueError, match="Expected Privacy and Signal to be created to run report got"
        ):
            runner.run(jobs_to_run=[JobKind.report])

    def test_delete_table(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.delete_table("test_table")
        assert "test_table" not in runner.config.tables.keys()

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
        assert runner.config.avatarization["test_table"].use_categorical_reduction == True
        assert runner.config.privacy_metrics["test_table"].ncp == 2
        assert runner.config.privacy_metrics["test_table"].use_categorical_reduction == True
        assert runner.config.signal_metrics["test_table"].ncp == 2
        assert runner.config.signal_metrics["test_table"].use_categorical_reduction == True

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
        assert runner.config.avatarization["test_table"].use_categorical_reduction == False

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
            exclude_replacement_strategy=ExcludeVariablesMethod.ROW_ORDER,
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

    def test_update_parameters_with_imputation(self):
        """Test updating imputation parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        # Set initial parameters
        runner.set_parameters("test_table", k=3, imputation_method=ImputeMethod.MEDIAN)

        # Update imputation method and add k parameter
        runner.update_parameters("test_table", imputation_method=ImputeMethod.KNN, imputation_k=5)

        # Verify imputation parameters were updated
        assert runner.config.avatarization["test_table"].imputation["method"] == "knn"
        assert runner.config.avatarization["test_table"].imputation["k"] == 5
        assert runner.config.avatarization["test_table"].k == 3  # Original k preserved

    def test_update_parameters_with_time_series(self):
        """Test updating time series parameters."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1, time_series_time="col1")
        # Set initial parameters
        runner.set_parameters(
            "test_table", k=3, time_series_nf=2, time_series_projection_type=ProjectionType.FCPA
        )

        # Update time series parameters
        runner.update_parameters(
            "test_table", time_series_method=AlignmentMethod.MEAN, time_series_nb_points=10
        )

        # Verify time series parameters were updated
        assert runner.config.time_series["test_table"].projection["nf"] == 2  # Preserved
        assert (
            runner.config.time_series["test_table"].projection["projection_type"] == "fcpa"
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
            closest_rate_percentage_threshold=0.8,
        )

        # Verify privacy metrics parameters were updated
        assert runner.config.privacy_metrics["test_table"].known_variables == ["col2"]
        assert runner.config.privacy_metrics["test_table"].target == "col1"
        assert runner.config.privacy_metrics["test_table"].closest_rate_percentage_threshold == 0.8
        assert runner.config.avatarization["test_table"].k == 3  # Original k preserved

    def test_update_parameters_when_nothing_was_set(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table")
        runner.update_parameters("test_table", ncp=5)

        assert runner.config.privacy_metrics["test_table"].ncp == 5
        assert runner.config.signal_metrics["test_table"].ncp == 5

    def test_extract_current_parameters_standard_avatarization(self):
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
            exclude_replacement_strategy=ExcludeVariablesMethod.COORDINATE_SIMILARITY,
            imputation_method=ImputeMethod.KNN,
            imputation_k=5,
            imputation_training_fraction=0.8,
            known_variables=["col1"],
            target="col2",
        )

        # Extract parameters
        current_params = runner._extract_current_parameters("test_table")

        # Verify extracted parameters match what was set
        assert current_params["k"] == 3
        assert current_params["ncp"] == 2
        assert current_params["use_categorical_reduction"] == True
        assert current_params["column_weights"] == {"col1": 0.7, "col2": 0.3}
        assert current_params["exclude_variable_names"] == ["col2"]
        assert (
            current_params["exclude_replacement_strategy"]
            == ExcludeVariablesMethod.COORDINATE_SIMILARITY
        )
        assert current_params["imputation_method"] == ImputeMethod.KNN
        assert current_params["imputation_k"] == 5
        assert current_params["imputation_training_fraction"] == 0.8
        assert current_params["known_variables"] == ["col1"]
        assert current_params["target"] == "col2"

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
        assert current_params["use_categorical_reduction"] == True
        assert "k" not in current_params

    def test_extract_current_parameters_time_series(self):
        """Test extracting parameters with time series configuration."""
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1, time_series_time="col1")
        runner.set_parameters(
            "test_table",
            k=3,
            time_series_nf=5,
            time_series_projection_type=ProjectionType.FCPA,
            time_series_nb_points=10,
            time_series_method=AlignmentMethod.MAX,
        )

        # Extract parameters
        current_params = runner._extract_current_parameters("test_table")

        # Verify time series parameters are extracted correctly
        assert current_params["time_series_nf"] == 5
        assert current_params["time_series_projection_type"] == ProjectionType.FCPA
        assert current_params["time_series_nb_points"] == 10
        assert current_params["time_series_method"] == AlignmentMethod.MAX
