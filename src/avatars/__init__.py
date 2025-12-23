__version__ = "1.12.0"

# Re-export main public entry points for convenience so users can do for example:
# from avatars import Manager, Runner, ApiClient
# Auto-install the crash handler for enhanced error reporting
from avatars import crash_handler as _crash_handler  # noqa: F401
from avatars.client import ApiClient  # noqa: F401
from avatars.manager import Manager  # noqa: F401
from avatars.runner import Runner  # noqa: F401

__all__ = [
    "__version__",
    "Manager",
    "ApiClient",
    "Runner",
]
