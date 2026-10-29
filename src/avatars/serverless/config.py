"""How a serverless ``Manager`` is configured.

Mirrors ``avatars.config.Config`` in shape -- a ``pydantic-settings`` model reading
``AVATAR_SERVERLESS_``-prefixed environment variables -- so that a notebook and a
container are configured the same way.

Nothing here is secret. The licence *key* passes through (it is the user's to
supply), but every decision about whether that key is valid, and what it permits,
happens inside the compiled engine. This module must never grow a signature check:
``services/client`` is mirrored verbatim into the public ``octopize/avatar-python``
repository on every release.
"""

import os
import secrets
import warnings
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_WORKDIR = Path.home() / ".avatar" / "serverless"

# Where a licence key is looked for, in precedence order, when one is not passed
# explicitly to `Manager`. The file forms are listed last but documented first: a
# notebook that reads its licence from a file stays shareable, whereas one with the
# token pasted into a cell leaks it into git.
LICENSE_ENV_VAR = "AVATAR_LICENSE_KEY"
LICENSE_FILENAME = "license.key"
HOME_LICENSE_PATH = Path.home() / ".avatar" / LICENSE_FILENAME


class ServerlessConfig(BaseSettings):
    """Settings for running the engine in-process."""

    model_config = SettingsConfigDict(
        env_prefix="AVATAR_SERVERLESS_",
        extra="ignore",
    )

    workdir: Path = DEFAULT_WORKDIR
    """Where inputs, results and the job index live.

    Defaults outside the notebook's working directory on purpose: re-running a
    notebook inside a git checkout should not drop a results tree into it, and
    ``create_runner_from_name`` wants somewhere stable to look after a restart.
    """

    license_key: str | None = None

    executor: Literal["serial", "threads"] = "serial"
    """Which in-process executor the engine uses.

    ``serial`` by default because that is what ``avatar/tests/integration`` runs and
    therefore the only one with coverage behind it. ``threads`` is exposed but
    undocumented until someone measures whether it actually helps.
    ``dask`` is deliberately not offered: a local Dask cluster spawns worker
    *processes*, which is the thing serverless mode exists to avoid.
    """

    batch_size: int | None = None
    """Rows per chunk. ``None`` leaves the engine's own default (2**17) alone."""

    pdf_generator_binary: str | None = None
    """The report renderer. ``None`` (the default) means: the one bundled in the engine
    wheel if present, otherwise ``reportgenerator`` from PATH. Without either, report
    jobs still finish but produce Typst source instead of a PDF."""

    @field_validator("workdir")
    @classmethod
    def _expand_home(cls, value: Path) -> Path:
        # `~/notebooks/wd` from a setting or an environment variable means the home.
        return value.expanduser()

    def resolve_license_key(self) -> str | None:
        """The licence key, from the first place that has one.

        Precedence is explicit argument (already folded into ``license_key`` by the
        caller) > environment > workdir file > home file. The engine decides whether
        what we found is *valid*; this only decides where to look.
        """
        if self.license_key:
            return self.license_key
        # Unprefixed, matching AVATAR_API_KEY: the licence is the serverless
        # credential, so it is named like the credential it replaces rather than like
        # a serverless tuning knob. AVATAR_SERVERLESS_LICENSE_KEY also works, via the
        # settings prefix, and takes precedence because it lands in `license_key`.
        from_env = os.environ.get(LICENSE_ENV_VAR, "").strip()
        if from_env:
            return from_env
        for candidate in (self.workdir / LICENSE_FILENAME, HOME_LICENSE_PATH):
            try:
                if candidate.is_file():
                    key = candidate.read_text().strip()
                    if key:
                        return key
            except (OSError, UnicodeDecodeError) as exc:
                # Not fatal: the next place may hold the key. But a licence file that
                # cannot be read deserves a word, or the user sees only "no licence".
                warnings.warn(f"could not read the licence file {candidate}: {exc}", stacklevel=2)
                continue
        return None


def new_seeding_salt() -> int:
    """A fresh salt, for a workdir that has never had one.

    Range matches ``avatar.config.Config.SEEDING_SALT``.
    """
    return secrets.randbelow(2**31)
