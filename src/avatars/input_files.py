"""The files already in the input directory of a user, which a table can reuse.

A table declared from an :class:`InputFile` is not uploaded again: the
configuration names the stored file, and the job reads it from the storage.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

RETENTION_SEGMENT = re.compile(r"^(\d+)d$")


@dataclass(frozen=True)
class InputFile:
    """A file of the input directory, as the storage reports it.

    Build one by hand with its name alone to reuse a file without a listing:
    ``InputFile("patients.csv")``. ``Runner.add_table`` checks that the file is in
    the storage before it declares the table.
    """

    name: str
    """The file name, without the directory."""
    size: int | None = None
    """Its size in bytes."""
    uploaded_at: datetime | None = None
    expires_at: datetime | None = None
    """When the retention rule of the storage removes it, if the rule is known."""


class InputFiles(Mapping[str, InputFile]):
    """The files of the input directory, newest first, by name.

    ``files["patients.csv"]`` is the file of that name; a missing name raises a
    ``KeyError`` that lists the names there are.
    """

    def __init__(self, files: list[InputFile], retention_days: int | None = None) -> None:
        ordered = sorted(files, key=_upload_time, reverse=True)
        self._files = {file.name: file for file in ordered}
        self.retention_days = retention_days
        """How long the storage keeps a file after its upload, when the layout says."""

    def __getitem__(self, name: str) -> InputFile:
        try:
            return self._files[name]
        except KeyError:
            raise KeyError(missing_file_message(name, self._files)) from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._files)

    def __len__(self) -> int:
        return len(self._files)

    def __repr__(self) -> str:
        return f"InputFiles({list(self._files)!r})"


def missing_file_message(name: str, stored: Iterable[str]) -> str:
    """Why ``name`` cannot be reused: it is not among the ``stored`` file names."""
    names = ", ".join(stored) or "none"
    return f"No file named {name!r} in your storage. Stored files: {names}"


def retention_days_of(directory_url: str) -> int | None:
    """The retention window a directory is filed under.

    The API lays a user's area out as ``s3://<bucket>/<days>d/...``, so
    ``s3://u/30d/org/u/input`` keeps its files 30 days.
    """
    segments = [segment for segment in urlparse(directory_url).path.split("/") if segment]
    if not segments:
        return None
    match = RETENTION_SEGMENT.match(segments[0])
    return int(match.group(1)) if match else None


def input_files_listing(directory_url: str, entries: list[dict[str, Any]]) -> InputFiles:
    """What an fsspec listing of ``directory_url`` comes to.

    ``entries`` are the detailed entries of ``fs.ls(directory, detail=True)``.
    Directories are left out.
    """
    retention_days = retention_days_of(directory_url)
    files = []
    for entry in entries:
        if entry.get("type") == "directory":
            continue
        uploaded_at = _modified_at(entry)
        expires_at = (
            uploaded_at + timedelta(days=retention_days)
            if uploaded_at is not None and retention_days is not None
            else None
        )
        files.append(
            InputFile(
                name=str(entry["name"]).rstrip("/").rsplit("/", 1)[-1],
                size=entry.get("size"),
                uploaded_at=uploaded_at,
                expires_at=expires_at,
            )
        )
    return InputFiles(files, retention_days=retention_days)


def _modified_at(entry: dict[str, Any]) -> datetime | None:
    """The modification time of an fsspec entry: S3 gives a datetime, a local disk a timestamp."""
    last_modified = entry.get("LastModified")
    if isinstance(last_modified, datetime):
        return last_modified if last_modified.tzinfo else last_modified.replace(tzinfo=UTC)
    mtime = entry.get("mtime")
    if isinstance(mtime, int | float):
        return datetime.fromtimestamp(mtime, tz=UTC)
    return None


def _upload_time(file: InputFile) -> datetime:
    return file.uploaded_at or datetime.min.replace(tzinfo=UTC)
