import os
import time
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from avatars.manager import Manager
from avatars.models import JobKind
from avatars.runner import Results
from tests.conftest import FakeApiClient


class TestRunner:
    manager: Manager
    df1 = pd.DataFrame({
        'col1': [1, 2, 3, 4, 5],
        'col2': [3, 4, 5, 6, 7]
    })
    df_parent = pd.DataFrame({'id': [1, 2], 'col2': [3, 4]})
    df_child = pd.DataFrame({'id': [1, 2, 3], 'id2': [1, 2, 1], 'val': [5, 6, 7], 'col2': [3, 4, 5]})

    @classmethod
    def setup_class(cls):
        cls.manager = Manager("http://localhost:8000", FakeApiClient())

    def test_add_table_df(self):
        runner=self.manager.create_runner()
        runner.add_table("test_table", data=self.df1)
        assert "test_table" in runner.config.tables.keys()

    def test_add_table_from_file(self):
        runner=self.manager.create_runner()
        runner.add_table("test_table", data="../api/src/integration_test/fixtures/iris.csv")
        assert "test_table" in runner.config.tables.keys()

    def test_add_link(self):
        runner=self.manager.create_runner()
        runner.add_table("parent", data=self.df_parent ,primary_key="id")
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.add_link("parent","id",  "child" , "id2")
        assert len(runner.config.tables.keys()) == 2
        assert len(runner.config.tables["parent"].links) == 1

    def test_set_parameters(self):
        runner=self.manager.create_runner()
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3, ncp=2)
        assert len(runner.config.avatarization.keys()) == 1
        assert len(runner.config.privacy_metrics.keys()) == 1
        assert len(runner.config.signal_metrics.keys()) == 1

    def test_run(self):
        runner=self.manager.create_runner()
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run()
        assert list(runner.jobs.keys()) == [JobKind.standard, JobKind.signal_metrics, JobKind.privacy_metrics, JobKind.report]

    def test_run_order(self):
        runner=self.manager.create_runner()
        runner.add_table("test_table", data=self.df1)
        runner.set_parameters("test_table", k=3)
        runner.run([JobKind.signal_metrics, JobKind.privacy_metrics, JobKind.standard])
        # test the order of job creation
        assert list(runner.jobs.keys()) == [JobKind.standard, JobKind.signal_metrics, JobKind.privacy_metrics]

    def test_multitable(self):
        runner=self.manager.create_runner()
        runner.add_table("parent", data=self.df_parent ,primary_key="id", individual_level=True)
        runner.add_table("child", data=self.df_child, primary_key="id", foreign_keys=["id2"])
        runner.set_parameters("parent", k=1)
        runner.set_parameters("child", k=1)
        runner.add_link("parent","id",  "child" , "id2")
        runner.run()
        assert list(runner.config.tables.keys()) == ['parent', 'child']
        assert len(runner.config.tables["parent"].links) == 1
        assert list(runner.jobs.keys()) == [JobKind.standard, JobKind.signal_metrics, JobKind.privacy_metrics] # report is not run when multiple tables are used

    def test_get_all_results(self):
        runner=self.manager.create_runner()
        runner.add_table("parent", data=self.df_parent ,primary_key="id", individual_level=True)
        runner.set_parameters("parent", k=1)
        runner.run()
        runner.get_all_results()
        assert len(runner.results.keys()) == 4
        assert list(runner.results.keys()) == [JobKind.standard, JobKind.signal_metrics, JobKind.privacy_metrics, JobKind.report]
        assert len(runner.results[JobKind.standard].keys()) == 1
        for table in runner.results[JobKind.standard].keys():
            assert isinstance(runner.results[JobKind.standard][table][Results.SHUFFLED], pd.DataFrame)
            assert isinstance(runner.results[JobKind.standard][table][Results.UNSHUFFLED], pd.DataFrame)
            assert isinstance(runner.results[JobKind.privacy_metrics][table][Results.PRIVACY_METRICS], list)
            assert isinstance(runner.results[JobKind.signal_metrics][table][Results.SIGNAL_METRICS], list)
