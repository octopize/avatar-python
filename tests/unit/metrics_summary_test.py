import pandas as pd

from avatars.metrics_summary import build_metrics_summary_df

MetricsSummary = dict[str, dict[str, float | None]]


class TestBuildMetricsSummaryDf:
    def test_multiple_tables(self):
        privacy: MetricsSummary = {"t1": {"ref_a": 0.9}, "t2": {"ref_b": 0.5}}
        signal: MetricsSummary = {"t1": {"ref_a": 0.7}, "t2": {"ref_b": 0.4}}
        df = build_metrics_summary_df(privacy, signal)
        assert len(df) == 2
        assert set(df.index) == {"t1", "t2"}

    def test_rows_are_sorted(self):
        privacy: MetricsSummary = {"t2": {"ref_b": 0.5}, "t1": {"ref_a": 0.9}}
        signal: MetricsSummary = {"t2": {"ref_b": 0.4}, "t1": {"ref_a": 0.7}}
        df = build_metrics_summary_df(privacy, signal)
        assert df.index[0] == "t1"
        assert df.index[1] == "t2"

    def test_missing_privacy_value(self):
        privacy: MetricsSummary = {"t1": {"ref_a": 0.9}}
        signal: MetricsSummary = {"t1": {"ref_a": 0.7, "ref_b": 0.6}}
        df = build_metrics_summary_df(privacy, signal)
        assert pd.isna(df.loc["t1", ("ref_b", "privacy")])
        assert df.loc["t1", ("ref_b", "signal")] == 0.6

    def test_missing_signal_value(self):
        privacy: MetricsSummary = {"t1": {"ref_a": 0.9, "ref_b": 0.8}}
        signal: MetricsSummary = {"t1": {"ref_a": 0.7}}
        df = build_metrics_summary_df(privacy, signal)
        assert pd.isna(df.loc["t1", ("ref_b", "signal")])
        assert df.loc["t1", ("ref_b", "privacy")] == 0.8

    def test_empty_inputs(self):
        df = build_metrics_summary_df({}, {})
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_none_metric_value(self):
        privacy: MetricsSummary = {"t1": {"ref_a": None}}
        signal: MetricsSummary = {"t1": {"ref_a": 0.5}}
        df = build_metrics_summary_df(privacy, signal)
        assert pd.isna(df.loc["t1", ("ref_a", "privacy")])
        assert df.loc["t1", ("ref_a", "signal")] == 0.5

    def test_keys_union_across_tables(self):
        privacy: MetricsSummary = {"t1": {"ref_a": 0.9}}
        signal: MetricsSummary = {"t2": {"ref_b": 0.4}}
        df = build_metrics_summary_df(privacy, signal)
        assert len(df) == 2
        assert pd.isna(df.loc["t1", ("ref_b", "signal")])
        assert pd.isna(df.loc["t2", ("ref_a", "privacy")])
