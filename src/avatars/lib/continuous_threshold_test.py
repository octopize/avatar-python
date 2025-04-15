import pandas as pd

from avatars.lib.continuous_threshold import get_continuous_under_threshold


def test_get_continuous_under_threshold() -> None:
    """Check the variable selection with a threshold."""
    df = pd.DataFrame({"variable_1": [1, 1, 2], "variable_2": [1, 2, 3]})

    variables = get_continuous_under_threshold(df, threshold=2)
    expected = ["variable_1"]

    assert variables == expected
