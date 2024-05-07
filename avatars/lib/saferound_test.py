"""Original source: https://github.com/cgdeboer/iteround."""

from collections import OrderedDict
from typing import NamedTuple
from typing import OrderedDict as OrderedDictType
from typing import Tuple

import pytest

from avatars.lib.saferound import RoundingStrategy, saferound


class Setup(NamedTuple):
    in_list: list[float]
    in_dict: dict[str, float]
    in_odict: OrderedDictType[str, float]
    in_tuple: Tuple[float, float, float]
    neg_in_list: list[float]
    huge_in_list: list[float]


@pytest.fixture
def setup() -> Setup:
    in_list = [4.0001, 3.2345, 3.2321, 6.4523, 5.3453, 7.3422]
    in_dict = {
        "foo": 60.19012964572332,
        "bar": 15.428802458406679,
        "baz": 24.381067895870007,
    }
    in_odict = OrderedDict(in_dict)
    in_tuple = (60.1901296, 15.42880, 24.38106789)

    neg_in_list = [x * -1.0 for x in in_list]
    huge_in_list = [x * 100000.0 for x in in_list]
    setup = Setup(in_list, in_dict, in_odict, in_tuple, neg_in_list, huge_in_list)
    return setup


def test_basic_difference(setup: Setup) -> None:
    out = [4.0, 3.24, 3.23, 6.45, 5.35, 7.34]
    assert saferound(setup.in_list, 2) == out


def test_basic_largest(setup: Setup) -> None:
    out = [4.0, 3.23, 3.23, 6.45, 5.35, 7.35]
    assert saferound(setup.in_list, 2, RoundingStrategy.LARGEST) == out


def test_basic_smallest(setup: Setup) -> None:
    out = [4.0, 3.24, 3.23, 6.45, 5.35, 7.34]
    assert saferound(setup.in_list, 2, RoundingStrategy.SMALLEST) == out


def test_dict(setup: Setup) -> None:
    out = {"foo": 60.0, "bar": 16.0, "baz": 24.0}
    assert saferound(setup.in_dict, 0) == out


def test_odict(setup: Setup) -> None:
    out = OrderedDict({"foo": 60.0, "bar": 16.0, "baz": 24.0})
    assert saferound(setup.in_odict, 0) == out


def test_tuple(setup: Setup) -> None:
    out = (60.0, 16.0, 24.0)
    assert saferound(setup.in_tuple, 0) == out


def test_error_bad_float() -> None:
    bad = ["a", 3.2345, 3.2321, 6.4523, 5.3453, 7.3422]
    with pytest.raises(ValueError, match="all values in the iterable to be float"):
        saferound(bad, 2)


def test_error_bad_strategy(setup: Setup) -> None:
    with pytest.raises(ValueError, match="valid RoundingStrategy"):
        saferound(setup.in_list, 2, strategy="bad")  # type: ignore[arg-type]


def test_negative(setup: Setup) -> None:
    out = [-4.0, -3.24, -3.23, -6.45, -5.35, -7.34]
    assert saferound(setup.neg_in_list, 2) == out


def test_huge(setup: Setup) -> None:
    out = [400000.0, 324000.0, 323000.0, 645000.0, 535000.0, 734000.0]
    assert saferound(setup.huge_in_list, -3) == out


def test_overround(setup: Setup) -> None:
    out = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert saferound(setup.in_list, -3) == out


def test_over_with_sum(setup: Setup) -> None:
    out = [0.0, 0.0, 0.0, 10.0, 10.0, 10.0]
    assert saferound(setup.in_list, -1) == out


def test_topline(setup: Setup) -> None:
    out = [4.0, 3.0, 3.0, 7.0, 5.0, 7.0]
    topline = 29
    actual_out: list[float] = saferound(setup.in_list, 0, topline=topline)
    actual_topline = sum(actual_out)
    assert actual_out == out
    assert topline == actual_topline


def test_topline_sum(setup: Setup) -> None:
    assert sum(saferound(setup.in_list, 0, topline=28)) == 28
    assert sum(saferound(setup.in_list, 0, topline=29)) == 29
    assert sum(saferound(setup.in_list, 0, topline=30)) == 30


def test_empty_returns_empty() -> None:
    out: list[float] = []
    topline = 1
    actual_out = saferound([], 0, topline=topline)
    assert actual_out == out
