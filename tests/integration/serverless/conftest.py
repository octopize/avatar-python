"""A real, signed licence for the serverless integration tests.

Serverless mode refuses to start without one -- which is the point of it -- so these
tests mint their own, with a key the engine trusts:

- against the engine installed from source, a throwaway key generated per session and
  registered in ``avatar.licensing.keys.PUBLIC_KEYS``, the table a source checkout reads;
- against a compiled engine, which trusts only the keys stamped into it, the key it was
  built with, read from the file that ``AVATAR_LICENSE_SIGNING_KEY_FILE`` names (CI sets it).

Nothing here touches or needs the real signing key.
"""

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip(
    "avatar",
    reason="needs the engine: `just install-serverless`, or an engine bundle",
)

from avatar.licensing import hybrid, keys
from avatar.licensing.runtime import clear_active
from avatar.licensing.token import (
    LicenseHeader,
    LicensePayload,
    b64url_decode,
    b64url_encode,
    encode,
    signing_input,
)
from avatar.models.feature_scope import FeatureScope, feature_scope_unlimited


@pytest.fixture(autouse=True)
def _clear_licence_between_tests() -> Iterator[None]:
    clear_active()
    yield
    clear_active()


@pytest.fixture(scope="session")
def signing_key() -> Iterator[hybrid.PrivateKey]:
    key_file = os.environ.get("AVATAR_LICENSE_SIGNING_KEY_FILE")
    if key_file:
        private = hybrid.PrivateKey(b64url_decode(Path(key_file).read_text().strip()))
    else:
        private = hybrid.PrivateKey.generate()
    keys.PUBLIC_KEYS[private.key_id] = b64url_encode(private.public_key)
    yield private
    keys.PUBLIC_KEYS.pop(private.key_id, None)


@pytest.fixture
def make_license(signing_key: hybrid.PrivateKey) -> Callable[..., str]:
    """Mint a licence. Unlimited by default; narrow it to test a refusal."""

    def _make(
        *,
        feature_scopes: list[FeatureScope] | None = None,
        max_lines: int = 2**31 - 1,
        max_dimensions: int = 2000,
        expires_in: timedelta = timedelta(days=30),
    ) -> str:
        now = datetime.now(UTC)
        header = LicenseHeader(alg=hybrid.ALGORITHM, kid=signing_key.key_id)
        payload = LicensePayload(
            sub=f"user:{uuid4()}",
            user_email="integration@octopize.test",
            org_id=str(uuid4()),
            org_name="Integration Test",
            jti=str(uuid4()),
            iat=int(now.timestamp()),
            nbf=int(now.timestamp()),
            exp=int((now + expires_in).timestamp()),
            license_type="octopize",
            feature_scopes=feature_scopes or list(feature_scope_unlimited),
            max_allowed_lines_per_dataset=max_lines,
            max_allowed_dimensions_per_dataset=max_dimensions,
        )
        token: str = encode(header, payload, signing_key.sign(signing_input(header, payload)))
        return token

    return _make


@pytest.fixture
def license_key(make_license: Callable[..., str]) -> str:
    return make_license()
