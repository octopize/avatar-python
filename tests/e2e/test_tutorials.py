import os
import pathlib
import runpy

import pytest

# Set the working directory to the project root
project_root = pathlib.Path(__file__).parent.parent.parent
os.chdir(project_root)

tutorials = project_root / "notebooks"
tutorials_path = tutorials.resolve().glob("*.py")


@pytest.mark.parametrize("script", tutorials_path, ids=lambda x: x.name)
def test_script_execution(script):
    # Set the working directory to the notebooks folder
    notebooks_dir = pathlib.Path(__file__).parent.parent.parent / "notebooks"
    os.chdir(notebooks_dir)

    # Use non-interactive matplotlib backend to avoid opening windows during tests
    os.environ["MPLBACKEND"] = "Agg"

    # Run the script
    runpy.run_path(script)
