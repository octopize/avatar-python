import pandas as pd
import pytest
from avatar_yaml.models.schema import ColumnType

from avatars.manager import Manager
from avatars.models import JobKind
from avatars.runner import Results
from tests.conftest import FakeApiClient


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

    def test_set_parameters_with_dp(self):
        runner = self.manager.create_runner("test")
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", dp_epsilon=3, ncp=2)
        assert len(runner.config.avatarization.keys()) == 0
        assert len(runner.config.avatarization_dp.keys()) == 1
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1

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
        ]  # report is not run when multiple tables are used

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
