from __future__ import annotations

import itertools
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from inspect import signature
from typing import Any, Callable, Generator, Optional, TypeVar, get_args
from toolz.dicttoolz import valfilter, valmap

T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")


@dataclass
class TypeCheckInfo:
    result: bool = True
    reason: Optional[str] = None


def check_type(
    left_type: type[T], right_type: type[U], label: str = ""
) -> TypeCheckInfo:
    info = TypeCheckInfo(result=True if left_type == right_type else False)

    if not info.result:
        info.reason = f"Expected '{left_type}', got '{right_type}' instead"

    if info.reason and label:
        info.reason = f"{label}: {info.reason}"

    return info


def check_types(left: list[type[T]], right: list[type[U]]) -> TypeCheckInfo:
    info = TypeCheckInfo()

    if len(left) != len(right):
        info = TypeCheckInfo(
            result=False,
            reason=f"Expected {len(left)} arguments, got {len(right)} instead",
        )
    else:
        for arg in zip(itertools.count(), left, right):
            info = check_type(arg[1], arg[2], f"argument {arg[0]}")

            if not info.result:
                break

    return info


@dataclass
class FunctionInfo:
    args: list[type[Any]]
    ret: Any

    def arg_count(self) -> int:
        return len(self.args)

    def __eq__(self, other: object) -> bool | Any:
        if not isinstance(other, FunctionInfo):
            return NotImplemented

        args_info = check_types(self.args, other.args)
        ret_info = check_type(self.ret, other.ret)

        return args_info.result and ret_info.result


def callable_type_info(callable_type: type[T]) -> FunctionInfo:
    args = get_args(callable_type)

    return FunctionInfo(args=args[0], ret=args[1])


def function_info(func: Callable[..., R]) -> FunctionInfo:
    sig = signature(func, eval_str=True)  # type: ignore[call-arg]
    args = [a.annotation for a in sig.parameters.values()]

    return FunctionInfo(args=args, ret=sig.return_annotation)


def callable_type_match(callable_type: type[T], func: Callable[..., R]) -> bool:
    return callable_type_info(callable_type) == function_info(func)


def callable_match(left: Callable[..., R], right: Callable[..., R]) -> bool:
    return function_info(left) == function_info(right)


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
