__version__ = "1.29.0"

# Re-export main public entry points for convenience so users can do for example:
# Auto-install the crash handler for enhanced error reporting
from avatar_yaml import ConstantStrategy as ConstantStrategy
from avatar_yaml import FakeDataStrategy as FakeDataStrategy
from avatar_yaml import HashSha256Strategy as HashSha256Strategy
from avatar_yaml import IntegerStrategy as IntegerStrategy
from avatar_yaml import PiiType as PiiType
from avatar_yaml import PseudonymizationStrategy as PseudonymizationStrategy
from avatar_yaml import SpecificIdLetterCase as SpecificIdLetterCase
from avatar_yaml import SpecificIdStrategy as SpecificIdStrategy
from avatar_yaml import Uuid4Strategy as Uuid4Strategy

from avatars import crash_handler as _crash_handler  # noqa: F401
from avatars.client import ApiClient
from avatars.manager import Manager
from avatars.models import JobStatus
from avatars.runner import Runner

__all__ = [
    "ApiClient",
    "ConstantStrategy",
    "FakeDataStrategy",
    "HashSha256Strategy",
    "IntegerStrategy",
    "JobStatus",
    "Manager",
    "PiiType",
    "PseudonymizationStrategy",
    "Runner",
    "SpecificIdLetterCase",
    "SpecificIdStrategy",
    "Uuid4Strategy",
    "__version__",
]
