from __future__ import annotations

import io
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


def has_method(obj: Any, name: str) -> bool:
    return hasattr(obj, name) and callable(getattr(obj, name))


def is_file_like(obj: Any) -> bool:
    return has_method(obj, "read") and has_method(obj, "write")


def is_text_file(obj: Any) -> bool:
    # Cannot test solely on inheritance because of TemporaryFileWrapper for example
    return is_file_like(obj) and hasattr(obj, "mode") and "b" not in obj.mode


def is_text_buffer(obj: Any) -> bool:
    return isinstance(obj, io.TextIOBase)


def is_text_file_or_buffer(obj: Any) -> bool:
    # Cannot test solely on inheritance because of TemporaryFileWrapper for example
    return is_text_file(obj) or is_text_buffer(obj)
