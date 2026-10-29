"""Licence activation against the engine: the build end date, and what is shown."""

import warnings
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip(
    "avatar",
    reason="needs the engine: `just install-serverless`, or an engine bundle",
)

from avatar.licensing.build_expiry import build_expires_at

from avatars.serverless.engine import BUILD_END_WARNING_DAYS, activate_license


def _build_ending_in(days: int, monkeypatch: pytest.MonkeyPatch) -> None:
    end = datetime.now(UTC) + timedelta(days=days, hours=12)
    monkeypatch.setattr("avatar.licensing.build_expiry.build_expires_at", end.timestamp)


def test_a_build_ending_soon_is_announced(
    make_license: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_ending_in(BUILD_END_WARNING_DAYS - 1, monkeypatch)
    with pytest.warns(UserWarning, match="stops computing"):
        limits = activate_license(make_license())
    assert limits.engine_build_ends is not None


def test_a_build_far_from_its_end_says_nothing(
    make_license: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_ending_in(BUILD_END_WARNING_DAYS + 30, monkeypatch)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        activate_license(make_license())
    assert not [w for w in caught if "stops computing" in str(w.message)]


def test_a_source_engine_has_no_end_date(make_license: Callable[..., str]) -> None:
    if build_expires_at() != float("inf"):
        pytest.skip("a compiled engine has an end date, stamped at build")
    assert activate_license(make_license()).engine_build_ends is None
