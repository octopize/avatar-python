from __future__ import annotations

from contextlib import contextmanager
from enum import Enum
from typing import Any, Generator, Optional, TypeVar

from toolz.dicttoolz import valfilter, valmap

T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")


class ContentType(Enum):
    MULTIPART_FROM_DATA = "multipart/form-data"
    CSV = "text/csv"
    PDF = "application/pdf"
    JSON = "application/json"
    OCTET_STREAM = "application/octet-stream"
    ARROW_STREAM = "application/vnd.apache.arrow.stream"
    UNSUPPORTED = "unsupported"

    @classmethod
    def _missing_(cls, value: object) -> ContentType:
        return ContentType.UNSUPPORTED


def ensure_valid(what: Optional[T], label: str = "") -> T:
    if what is None:
        msg = f"{label} " if label else ""
        raise RuntimeError(f"Expected valid {msg} argument, got None instead")

    return what


@contextmanager
def validated(what: Optional[T], label: str = "") -> Generator[T, None, None]:
    val = ensure_valid(what, label)
    yield val


def pop_or(content: dict[str, Any], key: str, default: T) -> T:
    val: T = default

    if key in content:
        val = content.pop(key)

    return val


def remove_optionals(params: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if params:
        # Remove params if they are set to None (allow handling of optionals)
        params = valfilter(lambda x: x is not None, params)
        params = valmap(lambda x: x.value if isinstance(x, Enum) else x, params)

    return params
