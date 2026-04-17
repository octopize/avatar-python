import pandas as pd


def build_metrics_summary_df(
    privacy: dict[str, dict[str, float | None]],
    signal: dict[str, dict[str, float | None]],
) -> pd.DataFrame:
    """Combine privacy and signal summary dicts into a single DataFrame.

    Parameters
    ----------
    privacy:
        Nested dict ``{table_name: {reference: meta_metric}}`` from the privacy metrics job.
    signal:
        Nested dict ``{table_name: {reference: meta_metric}}`` from the signal metrics job.

    Returns
    -------
    pd.DataFrame
        A DataFrame indexed by ``table_name`` with MultiIndex columns ``(reference, metric)``
        where the top level is the reference name and the second level is
        ``privacy`` or ``signal``.
    """

    all_refs = sorted({ref for d in (privacy, signal) for refs in d.values() for ref in refs})
    all_tables = sorted({table for d in (privacy, signal) for table in d})

    def to_frame(d: dict[str, dict[str, float | None]]) -> pd.DataFrame:
        df = pd.DataFrame(d).T
        df.index.name = ""
        df.columns.name = "reference"
        return df.reindex(index=all_tables, columns=all_refs)

    result = pd.concat({"privacy": to_frame(privacy), "signal": to_frame(signal)}, axis=1)
    result = result.swaplevel(axis=1).sort_index(axis=1)
    result.columns.names = ["table_name", ""]
    return result
