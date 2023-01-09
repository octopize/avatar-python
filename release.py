from pathlib import Path
import re
import enum
import typer
from re import Pattern, Match

app = typer.Typer()

class BumpType(enum.Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def get_version_pattern(key: str) -> Pattern:
    pattern = re.compile(f"{key} = \"(\d+)\.(\d+)\.(\d+)\"")
    return pattern

def bump(match: re.Match, bump_type: BumpType) -> str:
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))

    if bump_type == BumpType.MAJOR:
        return  f"{major+1}.0.0"
    if bump_type == BumpType.MINOR:
        return  f"{major}.{minor+1}.0"
    if bump_type == BumpType.PATCH:
        return  f"{major}.{minor}.{patch+1}"

def get_version_match(text: str, key : str) -> Match:
    pattern = get_version_pattern(key)
    return re.search(pattern, text)



def get_bumped_text_with_bumped_version(bump_type: BumpType, text: str, key: str):
    """Bump the version in SemVer syntax using the provided `bump_type`.

    Usage:
        get_bumped_version(BumpType.MAJOR, "awesome_version = 0.2.2", key = "awesome_version)

        returns

        "awesome_version = 1.0.0"
    """
    pattern = get_version_pattern(key)
    replaced = re.sub(pattern, lambda match: f"{key} = \"{bump(match, bump_type)}\"", text)
    return replaced

def bump_version_in_file(filename: Path, key: str, bump_type : BumpType = BumpType.PATCH) -> None:
    with open(filename, "r+") as file:
        content = file.read()
        new_content = get_bumped_text_with_bumped_version(bump_type, content, key)
        file.seek(0)
        file.write(new_content)

@app.command()
def bump_version(bump_type: BumpType = typer.Option(BumpType.PATCH, case_sensitive=False)):
    with open(Path("pyproject.toml")) as file:
        match = get_version_match(file.read(), "version")

    current_version = ".".join(match.groups())
    next_version = bump(match, bump_type)

    should_bump = typer.confirm(f"Upgrade version from {current_version} to {next_version}?")
    if not should_bump:
        raise typer.Abort()

    bump_version_in_file(Path("pyproject.toml"), key = "version", bump_type=bump_type)
    bump_version_in_file(Path("avatars/__init__.py"), key = "__version__", bump_type=bump_type)

if __name__ == "__main__":
    app()
