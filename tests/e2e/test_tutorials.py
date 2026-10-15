import os
import pathlib
import runpy

import pytest

# Set the working directory to the project root
project_root = pathlib.Path(__file__).parent.parent.parent
os.chdir(project_root)

tutorials = project_root / "notebooks"
tutorials_path = list(tutorials.resolve().glob("*.py"))

NOT_YET_RUNNABLE = "NOT_YET_RUNNABLE"
"""Marker a tutorial carries when it documents an API that is not released yet.

Such a notebook is still the deliverable -- it is what a reader learns from, and
it is the specification the client is written against -- so it lives here with
the others rather than somewhere it would drift from them. It is skipped, with
its own reason, until the call it demonstrates exists.
"""


def _skip_reason(script: pathlib.Path) -> str | None:
    """The marker's own explanation, or None when the tutorial should run."""
    for line in script.read_text(encoding="utf-8").splitlines():
        if NOT_YET_RUNNABLE in line:
            return str(line.split(NOT_YET_RUNNABLE, 1)[1].lstrip(": ").strip())
    return None


@pytest.mark.parametrize("script", tutorials_path, ids=lambda x: x.name)
def test_script_execution(script):
    reason = _skip_reason(script)
    if reason is not None:
        pytest.skip(f"{script.name}: {reason}")

    # Set the working directory to the notebooks folder
    notebooks_dir = pathlib.Path(__file__).parent.parent.parent / "notebooks"
    os.chdir(notebooks_dir)

    # Use non-interactive matplotlib backend to avoid opening windows during tests
    os.environ["MPLBACKEND"] = "Agg"

    # Run the script
    runpy.run_path(script)
