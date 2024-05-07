import pandas as pd
import pytest

from avatars.lib.split import (
    get_index_without_duplicated_modalities,
    get_split_for_batch,
)


def test_get_split_for_batch() -> None:
    df = pd.DataFrame(
        data={
            "a": [1, 3, 5, 1, 3, 5, 1, 3, 5, 1, 3, 5],
            "b": ["a", "b", "a", "a", "b", "a", "a", "b", "a", "a", "b", "a"],
        }
    )
    result = get_split_for_batch(df, row_limit=6, seed=42)

    training = pd.DataFrame(
        data={"a": [1, 3, 3, 1, 3, 5], "b": ["a", "b", "b", "a", "b", "a"]},
        index=[0, 1, 10, 3, 7, 2],
    )
    batch = pd.DataFrame(
        data={"a": [1, 3, 5, 1, 5, 5], "b": ["a", "b", "a", "a", "a", "a"]},
        index=[9, 4, 11, 6, 5, 8],
    )

    pd.testing.assert_frame_equal(result[0], training)
    pd.testing.assert_frame_equal(result[1][0], batch)


def test_get_split_for_batch_with_optimization() -> None:
    # the four first record are unique but only the two first should be kept by the subset process
    df = pd.DataFrame(
        data={
            "a": ["a", "b", "b", "a", "a", "b", "b", "a", "a", "b", "b", "a"],
            "b": ["A", "B", "B", "B", "A", "B", "B", "B", "A", "B", "B", "B"],
            "c": ["1", "2", "1", "1", "1", "2", "1", "1", "1", "2", "1", "1"],
        }
    )
    training, splits = get_split_for_batch(df, row_limit=6, seed=42)

    # the two first record should be the same of the original data and the other ones
    # should be randomly selected
    expected_training = pd.DataFrame(
        data={
            "a": ["a", "b", "b", "a", "a", "b"],
            "b": ["A", "B", "B", "B", "B", "B"],
            "c": ["1", "2", "1", "1", "1", "1"],
        },
        index=[0, 1, 10, 3, 7, 2],
    )
    expected_batch = pd.DataFrame(
        data={
            "a": ["b", "a", "a", "b", "b", "a"],
            "b": ["B", "A", "B", "B", "B", "A"],
            "c": ["2", "1", "1", "1", "2", "1"],
        },
        index=[9, 4, 11, 6, 5, 8],
    )
    pd.testing.assert_frame_equal(expected_training, training)
    pd.testing.assert_frame_equal(expected_batch, splits[0])


def test_get_split_for_batch_raise_error() -> None:
    df = pd.DataFrame(data={"a": [1, 3], "b": ["a", "b"]})

    with pytest.raises(
        ValueError, match="You have too much variability in your categorical data"
    ):
        get_split_for_batch(df, row_limit=2, seed=42)


def test_get_index_without_duplicated_modalities() -> None:
    df = pd.DataFrame({"a": [1, 2, 1, 3, 2, 1], "b": [1, 2, 3, 3, 2, 1]})

    expect = [0, 1, 2, 3]
    result = get_index_without_duplicated_modalities(df)
    assert expect, result
