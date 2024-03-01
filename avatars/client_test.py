from typing import Any, Callable, Dict, Optional
from unittest.mock import patch

import httpx
import pytest

from avatars.client import ApiClient
from avatars.conftest import RequestHandle, api_client_factory


@patch("httpx.Client")
def test_should_verify_ssl(mock_client: Any) -> None:
    base_url = "https://test.com"

    def do_request(api_client: ApiClient, **kwargs: Any) -> None:
        api_client.request("GET", base_url, **kwargs)

    # Verify default is set to True
    api_client = ApiClient(base_url=base_url, verify_auth=False)
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] == True
    mock_client.reset_mock()

    # Verify that the should_verify_ssl parameter is passed to the httpx.Client
    api_client = ApiClient(
        base_url=base_url, should_verify_ssl=False, verify_auth=False
    )
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] == False
    mock_client.reset_mock()


@pytest.mark.parametrize(
    "base_url",
    [
        '"https://test.com"',
    ],
)
def test_url_is_rejected_if_it_contains_quotes(base_url: str) -> None:
    # Note there is "quote" within the URL, usually an error related to system
    # env variable configuration.
    with pytest.raises(ValueError, match="not to contain quotes") as exc_info:
        api_client = ApiClient(base_url=base_url)


class TestClientRequest:
    @pytest.fixture(scope="session")
    def json_ok_response(self) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"message": "ok"})

        return handler

    def test_can_handle_standard_json_ok_response(
        self, json_ok_response: RequestHandle
    ) -> None:
        api_client = api_client_factory(json_ok_response)

        result = api_client.request("GET", "/health")

        assert result == {"message": "ok"}
