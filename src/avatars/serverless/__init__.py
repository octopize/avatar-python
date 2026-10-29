"""Running the Avatar engine in this process, with no server.

It needs the Avatar engine, which is not on PyPI: it comes in the engine bundle that
Octopize supplies with a licence, installed from the bundle directory with::

    pip install -r requirements.txt

It is selected at construction time::

    from avatars import Manager

    manager = Manager(serverless=True, license_key="...")
    runner = manager.create_runner("my_set")

Everything after that is the ordinary SDK: the same ``Runner``, the same results.
The only difference is that :class:`~avatars.serverless.client.ServerlessClient`
stands where the HTTP client normally stands, and jobs execute here rather than on
a cluster.

The split across this package is deliberate. Only :mod:`avatars.serverless.engine`
imports ``avatar``; everything else -- the workdir layout, the URL envelope, the job
store, the exception mapping, the client itself -- is ordinary Python that can be
tested without the extra installed. Anything requiring judgement belongs on the
engine-free side of that line.
"""

from avatars.serverless.client import NotAvailableOfflineError, ServerlessClient
from avatars.serverless.config import ServerlessConfig
from avatars.serverless.store import ServerlessStore
from avatars.serverless.workdir import Workdir

__all__ = [
    "NotAvailableOfflineError",
    "ServerlessClient",
    "ServerlessConfig",
    "ServerlessStore",
    "Workdir",
]
