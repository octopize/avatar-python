from subprocess import PIPE
import subprocess
from pathlib import Path
import re
import enum
from typing import Any, Optional
import typer
from re import Pattern, Match

app = typer.Typer()

PYPROJECT_TOML = Path("pyproject.toml")
INIT_PY = Path("avatars/__init__.py")
CHANGELOG = Path("CHANGELOG.md")

KEY_MAPPING: dict[Path, str] = {
    PYPROJECT_TOML: "version",
    INIT_PY: "__version__",
}


class BumpType(enum.Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def get_version_pattern(key: str) -> Pattern:  # type: ignore[type-arg]
    pattern = re.compile(f'{key} = "(\d+)\.(\d+)\.(\d+)"') # noqa W905
    return pattern


def bump(match: re.Match, bump_type: BumpType) -> str:  # type: ignore[type-arg]
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))

    if bump_type == BumpType.MAJOR:
        return f"{major+1}.0.0"
    if bump_type == BumpType.MINOR:
        return f"{major}.{minor+1}.0"
    if bump_type == BumpType.PATCH:
        return f"{major}.{minor}.{patch+1}"

    raise ValueError(f"Expected valid bump_type, got {bump_type} instead.")


def get_version_match(text: str, key: str) -> Optional[Match]:  # type: ignore[type-arg]
    pattern = get_version_pattern(key)
    return re.search(pattern, text)


def get_bumped_text_with_bumped_version(
    bump_type: BumpType, text: str, key: str
) -> str:
    """Bump the version in SemVer syntax using the provided `bump_type`.

    Usage:
        get_bumped_version(BumpType.MAJOR, "awesome_version = 0.2.2", key = "awesome_version)

        returns

        "awesome_version = 1.0.0"
    """
    pattern = get_version_pattern(key)
    replaced = re.sub(
        pattern, lambda match: f'{key} = "{bump(match, bump_type)}"', text
    )
    return replaced


def bump_version_in_file(
    filename: Path, key: str, bump_type: BumpType = BumpType.PATCH
) -> None:
    with open(filename, "r+") as file:
        content = file.read()
        new_content = get_bumped_text_with_bumped_version(bump_type, content, key)
        file.seek(0)
        file.write(new_content)


def get_version_from_file(filename: Path) -> Optional[Match]:  # type: ignore[type-arg]
    with open(filename) as file:
        return get_version_match(file.read(), KEY_MAPPING[filename])


def _bump_version(bump_type: BumpType) -> None:
    version = get_version_from_file(PYPROJECT_TOML)

    if not version:
        raise ValueError(f"Could not read version from file {PYPROJECT_TOML}.")

    current_version = ".".join(version.groups())

    next_version = bump(version, bump_type)

    should_bump = typer.confirm(
        f"Upgrade version from {current_version} to {next_version}?"
    )
    if not should_bump:
        raise typer.Abort()

    bump_version_in_file(PYPROJECT_TOML, key="version", bump_type=bump_type)
    bump_version_in_file(INIT_PY, key="__version__", bump_type=bump_type)


def commit_and_tag() -> None:
    match = get_version_from_file(PYPROJECT_TOML)
    if not match:
        raise ValueError(f"Could not read version from file {PYPROJECT_TOML}.")

    new_version = ".".join(match.groups())

    commands = [
        ("git", "add", str(PYPROJECT_TOML), str(INIT_PY), str(CHANGELOG)),
        ("git", "commit", "-m", f"chore: release version {new_version}"),
        ("git", "tag", "-s", f"{new_version}", "-m", f"Release version {new_version}"),
    ]

    for command in commands:
        typer.echo(" ".join(command))
        result = subprocess.call(command)
        if result != 0:
            raise typer.Exit(result)


def push() -> None:
    commands = [
        ("git", "push"),
        ("git", "push", "--tags"),
    ]

    for command in commands:
        typer.echo(" ".join(command))
        result = subprocess.call(command)
        if result != 0:
            raise typer.Exit(result)


@app.command()
def bump_version(
    bump_type: BumpType = typer.Option(BumpType.PATCH, case_sensitive=False)
) -> Any:
    _bump_version(bump_type)


def check_preconditions() -> None:
    preconditions = [
        f"Have you updated the changelog at {CHANGELOG}?",
        "Have you generated the doc using `make doc`?",
    ]

    for condition in preconditions:
        result = typer.confirm(condition)
        if not result:
            raise typer.Abort()


@app.command()
def release(bump_type: BumpType = typer.Option(BumpType.PATCH)) -> Any:
    proc = subprocess.Popen(args=("git", "branch", "--show-current"), stdout=PIPE)
    stdout, _ = proc.communicate()

    current_branch = stdout.decode(encoding="utf-8")
    if not current_branch == "main":
        typer.echo(
            f"You can only run this on the 'main' branch. You are on {str(current_branch)}."
        )
        raise typer.Exit(1)

    check_preconditions()
    _bump_version(bump_type)
    commit_and_tag()
    push()


if __name__ == "__main__":
    app()