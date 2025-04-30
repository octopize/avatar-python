import numpy as np
import pandas as pd
import pytest

from avatars.processors import GeolocationNormalizationProcessor


@pytest.fixture
def df() -> pd.DataFrame:
    df = pd.read_csv("./fixtures/porto_taxi_200.csv")
    return df


@pytest.mark.skip(reason="copy from old client, failing due to the new API and new clien")
def test_preprocess(df: pd.DataFrame) -> None:
    processor = GeolocationNormalizationProcessor(
        latitude_variable="lat", longitude_variable="lon", n_reference_lat=10, n_bins=5
    )
    processed_df = processor.preprocess(df=df)

    assert len(processed_df) == len(df)


@pytest.mark.skip(reason="copy from old client, failing due to the new API and new clien")
def test_postprocess(df: pd.DataFrame) -> None:
    processor = GeolocationNormalizationProcessor(
        latitude_variable="lat", longitude_variable="lon", n_reference_lat=10, n_bins=5
    )
    random_points_df = df.sample(frac=0.25, replace=True).reset_index(drop=True)
    random_points_df["lon"] = np.random.uniform(0.0, 1.0, len(random_points_df))

    processor.preprocess(df=df)
    postprocessed_df = processor.postprocess(source=df, dest=random_points_df)

    assert len(postprocessed_df) == len(random_points_df)
    assert min(postprocessed_df["lon"]) >= min(df["lon"])
    assert max(postprocessed_df["lon"]) <= max(df["lon"])
