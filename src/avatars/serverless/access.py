"""The ``/access?url=`` envelope, reproduced for a client with no server.

``GET /results/{job}`` never hands out bare storage URLs. It wraps each one as
``{api}/access?url=<storage url>`` -- a ready-made call to the endpoint that mints
credentials for that file -- and the SDK passes the envelope straight back. This is
the API's own format (``services/api/src/api/domain/access_url.py``), reproduced
here because the SDK depends on it in five places that must keep working offline:

* ``DataUploader.upload_file_descriptor`` builds one itself from ``client.base_url``
  and hands it to ``results.get_permission_to_download``;
* ``DataUploader.download_file`` reads the ``url`` query parameter back out;
* ``FileDownloader.download_file`` takes the file extension off the tail of the
  envelope, so the storage path must be last;
* ``ResultsOrganizer.get_table_name`` reads ``Path(url).stem``;
* ``Runner.download_report`` defaults the output filename to ``Path(url).name``.

A bare ``file://`` URL satisfies none of those, which is why serverless mints the
same envelope rather than shortcutting to a path.
"""

from urllib.parse import parse_qs, urlparse

# The host the serverless client claims to be. Nothing ever connects to it: it exists
# so `pydantic_core.Url` parses the envelope and populates `.query`, which is what
# `DataUploader.download_file` reads. `.invalid` is reserved by RFC 6761 precisely so
# it can never resolve, which is the property we want -- a bug that turns one of
# these into a real request fails loudly instead of reaching someone else's server.
SERVERLESS_BASE_URL = "http://serverless.avatar.invalid/api"

_ENVELOPE_SCHEMES = frozenset({"http", "https"})


def map_to_access_url(base_url: str, storage_url: str) -> str:
    """Wrap a storage URL in the envelope the SDK expects from ``/results``."""
    return f"{base_url.rstrip('/')}/access?url={_escape_for_query(storage_url)}"


# Only the characters a query value cannot carry as they are: "%" first, so the others'
# escapes are not escaped again. Everything else stays readable, because the SDK reads
# a table's name off the end of this URL (`ResultsOrganizer.get_table_name`).
_QUERY_ESCAPES = (("%", "%25"), ("&", "%26"), ("#", "%23"), ("+", "%2B"))


def _escape_for_query(storage_url: str) -> str:
    for char, escape in _QUERY_ESCAPES:
        storage_url = storage_url.replace(char, escape)
    return storage_url


def unwrap_access_url(raw: str) -> str:
    """Return the storage URL an envelope carries.

    Anything that is not an envelope -- not on http(s), or carrying no ``url``
    parameter -- is returned unchanged, so a caller that already holds a storage URL
    can pass it through this function safely.

    Only one layer is removed, matching the API.
    """
    parsed = urlparse(raw)
    if parsed.scheme not in _ENVELOPE_SCHEMES:
        return raw
    carried = parse_qs(parsed.query).get("url", [])
    return carried[0] if carried and carried[0] else raw


def to_local_path(raw: str) -> str:
    """Resolve a storage URL or envelope to a plain local filesystem path.

    ``fsspec`` accepts ``file://`` happily, but ``pathlib`` and ``open`` do not, and
    the serverless client reads results with both.
    """
    storage_url = unwrap_access_url(raw)
    if storage_url.startswith("file://"):
        return storage_url[len("file://") :]
    return storage_url
