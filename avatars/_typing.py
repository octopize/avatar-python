from typing import (
    Any,
    Tuple,
    Literal,
    AnyStr,
    Protocol,
    TYPE_CHECKING,
)
from typing_extensions import TypeGuard, TypeAlias

if TYPE_CHECKING:
    from _typeshed import SupportsRead, SupportsWrite

    class FileLikeInterface(
        #! Make sure you modify is_file_like too.
        SupportsRead[AnyStr],
        SupportsWrite[AnyStr],
        Protocol,
    ):
        def seek(self, offset: int, whence: int = 0) -> int:
            pass


def is_file_like(obj: Any) -> TypeGuard["FileLikeInterface[AnyStr]"]:
    return hasattr(obj, "read") and hasattr(obj, "write") and hasattr(obj, "seek")


HttpxFile: TypeAlias = Tuple[Literal["file"], "FileLikeInterface[bytes]"]
