import pathlib
import runpy
import pytest

tutorials = pathlib.Path(__file__, "..").resolve().glob("Tutorial*.py")


@pytest.mark.parametrize("script", tutorials, ids=lambda x: x.stem)
def test_script_execution(script):
    runpy.run_path(script)
