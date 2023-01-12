import pandas as pd
import pytest

from avatars.processors import GroupModalitiesProcessor


def test_postprocess_noop(many_dtypes_df: pd.DataFrame) -> None:
    """Check postprocess doing nothing with high parameter."""
    processor = GroupModalitiesProcessor(
        min_unique=3, global_threshold=1, new_category="other"
    )
    pd.testing.assert_frame_equal(
        many_dtypes_df, processor.postprocess(many_dtypes_df, many_dtypes_df)
    )


def test_group_modalities_simple(many_dtypes_df: pd.DataFrame) -> None:
    """Check preprocess group all value to modality as expected."""
    processor = GroupModalitiesProcessor(
        min_unique=2, global_threshold=1, new_category="other"
    )

    df_processed = processor.preprocess(many_dtypes_df)

    expected = many_dtypes_df.copy()
    expected["strings"] = "other"

    pd.testing.assert_frame_equal(expected, df_processed)


def test_group_preprocess_min_unique(categorical_df: pd.DataFrame) -> None:
    """Verify min_unique and threshold parameter work as expected."""
    df = categorical_df
    processor = GroupModalitiesProcessor(
        min_unique=2, global_threshold=1, new_category="other"
    )

    df_processed = processor.preprocess(df)

    expected = df.copy()
    expected["variable_1"] = ["other", "blue", "blue", "other"]

    pd.testing.assert_frame_equal(expected, df_processed)


def test_group_preprocess_new_category(categorical_df: pd.DataFrame) -> None:
    """Check the new category parameter works as expected."""
    df = categorical_df
    processor = GroupModalitiesProcessor(
        min_unique=2, global_threshold=1, new_category="andere"
    )

    df_processed = processor.preprocess(df)

    expected = df.copy()
    expected["variable_1"] = ["andere", "blue", "blue", "andere"]

    pd.testing.assert_frame_equal(expected, df_processed)


def test_group_preprocess_variable_thresholds(categorical_df: pd.DataFrame) -> None:
    """Verify the variable_thresholds parameter works as expected."""
    df = categorical_df
    processor = GroupModalitiesProcessor(
        variable_thresholds={"variable_1": 1, "variable_2": 2}
    )

    df_processed = processor.preprocess(df)

    expected = df.copy()
    expected["variable_1"] = ["other", "blue", "blue", "other"]
    expected["variable_2"] = ["other", "other", "other", "other"]

    pd.testing.assert_frame_equal(expected, df_processed)


def test_wrong_variable_thresholds_raises_error(categorical_df: pd.DataFrame) -> None:
    """Verify that an unknown variable in variable_thresholds raises an error."""
    processor = GroupModalitiesProcessor(variable_thresholds={"wrong_variable": 3})
    df = categorical_df
    with pytest.raises(
        ValueError, match="Expected valid variables in variable_thresholds*"
    ):
        processor.preprocess(df=df)


def test_with_global_threshold_without_min_unique() -> None:
    """Verify that providing only global_threshold raises an error."""
    with pytest.raises(
        ValueError, match="Expected both of (global_threshold, min_unique)*"
    ):
        GroupModalitiesProcessor(global_threshold=10)


def test_with_min_unique_without_global_threshold() -> None:
    """Verify that providing only min_unique raises an error."""
    with pytest.raises(
        ValueError, match="Expected both of (global_threshold, min_unique)*"
    ):
        GroupModalitiesProcessor(min_unique=10)


def test_variables_with_multiple_threshold_parameters() -> None:
    """Verify that providing global_threshold and variable_thresholds together raises an error."""
    with pytest.raises(
        ValueError, match="Expected variable_thresholds or (threshold, min_unique)*"
    ):
        GroupModalitiesProcessor(
            variable_thresholds={"wrong_variable": 3},
            global_threshold=10,
            min_unique=40,
        )
