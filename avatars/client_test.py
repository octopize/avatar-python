from typing import Any, Dict
from unittest.mock import patch

import pytest

from avatars.client import ApiClient


@patch("httpx.Client")
def test_should_verify_ssl(mock_client: Any) -> None:
    base_url = "https://test.com"

    def do_request(api_client: ApiClient, **kwargs: Any) -> None:
        api_client.request("GET", base_url, verify_auth=False, **kwargs)  # type: ignore[arg-type]

    # Verify default is set to True
    api_client = ApiClient(base_url=base_url)
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] == True
    mock_client.reset_mock()

    # Verify that the should_verify_ssl parameter is passed to the httpx.Client
    api_client = ApiClient(base_url=base_url, should_verify_ssl=False)
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] == False
    mock_client.reset_mock()

    # Verify that the should_verify_ssl parameter is overriden by the one in request(), with False
    api_client = ApiClient(base_url=base_url, should_verify_ssl=True)
    # Override the call in the request() method
    do_request(api_client, should_verify_ssl=False)
    assert mock_client.call_args.kwargs["verify"] == False
    mock_client.reset_mock()

    # Verify that the should_verify_ssl parameter is overriden by the one in request(), with True
    api_client = ApiClient(base_url=base_url, should_verify_ssl=False)
    # Override the call in the request() method
    do_request(api_client, should_verify_ssl=True)
    assert mock_client.call_args.kwargs["verify"] == True
