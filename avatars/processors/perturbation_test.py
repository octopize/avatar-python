import numpy as np
import pandas as pd
import pytest

from avatars.processors import PerturbationProcessor


@pytest.mark.parametrize("perturbation_level", np.arange(0.1, 1, 0.1))
def test_does_perturb_continuous(perturbation_level: float) -> None:
    column = "a"
    source = pd.DataFrame([[0]], columns=[column])
    dest = pd.DataFrame([[1]], columns=[column])

    processor = PerturbationProcessor(perturbation_level={column: perturbation_level})
    expected = pd.DataFrame([[perturbation_level]], columns=[column])

    result = processor.postprocess(source, dest)
    pd.testing.assert_frame_equal(result, expected)


def test_does_perturb_categorical() -> None:
    column = "a"
    source = pd.DataFrame([1, 2, 3], columns=[column], dtype="object")
    dest = pd.DataFrame([10, 20, 30], columns=[column], dtype="object")

    processor = PerturbationProcessor(perturbation_level={column: 0.5}, seed=1)
    expected = pd.DataFrame([10, 20, 3], columns=[column], dtype="object")

    result = processor.postprocess(source, dest)
    pd.testing.assert_frame_equal(result, expected)


@pytest.mark.parametrize("perturbation_level", np.arange(0.1, 1, 0.1))
def test_categorical_proportions_are_respected(perturbation_level: float) -> None:
    """Verify that the perturbation level changes the proportion of avatars in the output."""
    shape = 100
    column = "a"

    source = pd.DataFrame(np.zeros(shape), columns=[column], dtype="object")
    dest = pd.DataFrame(np.ones(shape), columns=[column], dtype="object")

    processor = PerturbationProcessor(
        perturbation_level={column: perturbation_level}, seed=1
    )

    result = processor.postprocess(source, dest)

    # Counts the number of outputs that correspond to `dest` and make sure they are within
    # a certain tolerance.
    perturbed_counts = result.value_counts()[1.0]

    tolerance = 0.05
    upper_bound = shape * (perturbation_level + tolerance)
    lower_bound = shape * (perturbation_level - tolerance)

    assert lower_bound < perturbed_counts < upper_bound


def test_categorical_proportions_are_respected_edge_case() -> None:
    """Verify that a perturbation level of 1 and 0 keeps all and no perturbation."""
    shape = 10
    column = "a"

    source = pd.DataFrame(np.zeros(shape), columns=[column], dtype="object")
    dest = pd.DataFrame(np.ones(shape), columns=[column], dtype="object")

    # Perturbation level of one --> output should be the same as dest
    processor = PerturbationProcessor(perturbation_level={column: 1}, seed=1)
    result = processor.postprocess(source, dest)
    pd.testing.assert_frame_equal(dest, result)

    # Perturbation level of zero --> output should be the same as source
    processor = PerturbationProcessor(perturbation_level={column: 0}, seed=1)
    result = processor.postprocess(source, dest)
    pd.testing.assert_frame_equal(source, result)


def test_preprocess_noop(many_dtypes_df: pd.DataFrame) -> None:
    df = many_dtypes_df
    column = df.columns[0]
    processor = PerturbationProcessor(perturbation_level={column: 0.5})
    pd.testing.assert_frame_equal(df, processor.preprocess(df))


def test_missing_variable_raises_value_error(many_dtypes_df: pd.DataFrame) -> None:
    values = {"missing_variable": 1.0}
    processor = PerturbationProcessor(perturbation_level=values)
    with pytest.raises(ValueError, match="perturbation_level"):
        processor.postprocess(many_dtypes_df, many_dtypes_df)
