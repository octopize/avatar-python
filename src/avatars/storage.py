import os
from urllib.parse import urljoin, urlparse, urlunparse

import fsspec
import structlog

from avatars.config import config
from avatars.log import generate_logger_name, setup_logging

setup_logging()

logger = structlog.get_logger(generate_logger_name(__file__))


DEFAULT_FIND_LIMIT = 1000


def get_parent(uri: str) -> str:
    parsed_uri = urlparse(uri)
    parent_path = os.path.dirname(parsed_uri.path)
    return parsed_uri._replace(path=parent_path).geturl()


def get_filesystem(
    aws_access_key_id: str,
    aws_secret_access_key: str,
    storage_path: str,
) -> fsspec.AbstractFileSystem:
    """Get the filesystem implementation to the currently used storage backend.

    This function is a wrapper around `fsspec.filesystem` that handles the
    specific case of OVH storage.

    It will infer the correct filesystem implementation based on the `path`.

    For local paths, it will return a `LocalFileSystem`.
    For S3 paths, it will return a `S3FileSystem`.
    For GCS paths, it will return a `GCSFileSystem`.

    Parameters
    ----------
    config_shared_storage_path :
        The full path to where one should save the data.
        It should have a scheme that is equal to any prefix of the Prefix enum.

        For cloud providers, it expects a scheme, a bucket name, and a directory.
        The exact syntax is described at
        https://docs.octopize.io/docs/deploying/self-hosted/configuration
    """
    os.environ["FSSPEC_S3_ENDPOINT_URL"] = str(config.STORAGE_ENDPOINT_URL)
    # We set anon-Ture to avoid the need for credentials. If not specified, the
    # S3FileSystem will try to use the default credentials,
    # and expect the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables to be set.
    # Any value passed to these parameters will work.
    s3_fs_kwargs = {
        "anon": False,
        "client_kwargs": {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "endpoint_url": str(config.STORAGE_ENDPOINT_URL),
        },
    }
    filesystem, _ = fsspec.url_to_fs(storage_path, **s3_fs_kwargs)
    return filesystem


def get_full_path(path: str, *, base: str) -> str:
    """Get the fully qualified path to a file, including the domain, but without the scheme."""
    # Parse the base URL to remove the scheme

    parsed_base = urlparse(base)
    parsed_base_without_scheme = ("",) + parsed_base[1:]
    base_no_scheme = urlunparse(parsed_base_without_scheme)
    full_path = urljoin(base_no_scheme, path)

    return full_path
