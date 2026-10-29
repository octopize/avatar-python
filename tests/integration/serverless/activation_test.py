"""Licence activation against the engine: what it reports, from the licence alone."""

from collections.abc import Callable

import pytest

pytest.importorskip(
    "avatar",
    reason="needs the engine: `just install-serverless`, or an engine bundle",
)

from avatars.serverless.engine import activate_license


def test_activation_reports_the_licence(make_license: Callable[..., str]) -> None:
    """The engine reports the limits, the end date and the id of the licence it activated."""
    limits = activate_license(make_license(max_lines=1000))
    summary = limits.summary()
    assert summary.max_rows == 1000
    assert summary.expires_at == limits.expires_at
    assert summary.jti
