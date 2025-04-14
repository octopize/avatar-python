import io
from typing import (
    IO,
    Any,
    BinaryIO,
    Union,
)

DEFAULT_TIMEOUT = 5

FileLike = Union[BinaryIO, IO[Any], io.IOBase]
FileLikes = list[FileLike]
