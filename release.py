from typing import Tuple
from subprocess import PIPE
import subprocess
from pathlib import Path
import re
import enum
from typing import Any, Optional
from typing_extensions import TypeAlias
import typer
from re import Pattern, Match

app = typer.Typer()

PYPROJECT_TOML = Path("pyproject.toml")
INIT_PY = Path("avatars/__init__.py")

KEY_MAPPING: dict[Path, str] = {
    PYPROJECT_TOML: "version",
    INIT_PY: "__version__",
}


class BumpType(enum.Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def get_version_pattern(key: str) -> Pattern:  # type: ignore[type-arg]
    pattern = re.compile(f'{key} = "(\d+)\.(\d+)\.(\d+)"')  # noqa W905
    return pattern


def get_version_match(text: str, key: str) -> Optional[Match]:  # type: ignore[type-arg]
    pattern = get_version_pattern(key)
    return re.search(pattern, text)


def get_version_from_file(filename: Path) -> Optional[Match]:  # type: ignore[type-arg]
    with open(filename) as file:
        return get_version_match(file.read(), KEY_MAPPING[filename])


def commit_and_tag() -> None:
    match = get_version_from_file(PYPROJECT_TOML)
    if not match:
        raise ValueError(f"Could not read version from file {PYPROJECT_TOML}.")

    new_version = ".".join(match.groups())

    DoCommand: TypeAlias = list[str]
    UndoCommand: TypeAlias = list[str]
    commands: list[tuple[DoCommand, UndoCommand]] = [
        (
            [
                "git",
                "commit",
                "--allow-empty",
                "-m",
                f"chore: release version {new_version}",
            ],
            ["git", "reset", "HEAD^", "--soft"],
        ),
        (
            ["git", "tag", "-s", new_version, "-m", f"Release version {new_version}"],
            ["git", "tag", "-d", new_version],
        ),
    ]
    call_stack = []
    for do_undo_command in commands:
        call_stack.append(do_undo_command)
        do_command, undo_command = do_undo_command

        typer.echo(" ".join(do_command))
        do_result = subprocess.call(do_command)
        if do_result != 0:
            typer.echo(
                "Command produced non-zero exit status. Undoing previous commands..."
            )
            call_stack.pop()  # Remove currently executed commands that failed
            while call_stack:
                _, undo_command = call_stack.pop()
                typer.echo(" ".join(undo_command))
                undo_result = subprocess.call(undo_command)

                if undo_result:
                    typer.echo(
                        """Unexpected exception during undoing. """
                        """Git worktree is most likely in invalid state. Aborting..."""
                    )
                    raise typer.Exit(undo_result)
            typer.echo("Successfully undid previous commands.")
            raise typer.Exit(do_result)


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


def check_for_uncommitted_files() -> None:
    command = ("git", "ls-files", "-m")
    typer.echo(" ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)

    uncommitted_files = result.stdout.split("\n")[:-1]
    if len(uncommitted_files) == 0:
        typer.echo("All files are committed, proceeding")
    else:
        typer.echo(f"There are some uncommitted files: {uncommitted_files}.")
        result = typer.confirm(
            "You may commit some of them in another tab before proceeding. Proceed ?"
        )
        if not result:
            raise typer.Abort()


@app.command()
def release() -> Any:
    proc = subprocess.Popen(
        args=("git", "branch", "--show-current"), stdout=PIPE, text=True
    )
    current_branch, _ = proc.communicate()

    if not current_branch.strip() == "main":
        typer.echo(
            f"You can only run this on the 'main' branch. You are on '{current_branch}'."
        )
        raise typer.Exit(1)

    commit_and_tag()
    push()


if __name__ == "__main__":
    app()
