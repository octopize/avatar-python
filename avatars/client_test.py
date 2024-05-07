import unittest
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from avatars.client import ApiClient
from avatars.conftest import RequestHandle, api_client_factory, mock_httpx_client


@patch("httpx.Client")
def test_should_verify_ssl(mock_client: Any) -> None:
    base_url = "https://test.com"

    def do_request(api_client: ApiClient, **kwargs: Any) -> None:
        api_client.request("GET", base_url, **kwargs)

    # Verify default is set to True
    api_client = ApiClient(
        base_url=base_url, verify_auth=False, should_verify_compatibility=False
    )
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] is True
    mock_client.reset_mock()

    # Verify that the should_verify_ssl parameter is passed to the httpx.Client
    api_client = ApiClient(
        base_url=base_url,
        should_verify_ssl=False,
        verify_auth=False,
        should_verify_compatibility=False,
    )
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] is False
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
    with pytest.raises(ValueError, match="not to contain quotes"):
        ApiClient(base_url=base_url)


@pytest.mark.parametrize(
    "incompatiblity_status",
    [
        "incompatible",
        "unknown",
    ],
)
def test_should_verify_compatibility(incompatiblity_status: str) -> None:
    json = {
        "message": "Message from the server",
        "status": incompatiblity_status,
        "most_recent_compatible_client": "1.0.0",
    }

    http_client = mock_httpx_client(
        handler=lambda request: httpx.Response(200, json=json)
    )

    with pytest.warns(match="Client is not compatible"):
        ApiClient(
            base_url="http://localhost:8000",
            http_client=http_client,
            verify_auth=False,
            should_verify_compatibility=True,
        )


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

    def test_retries_on_ssl_eof_error(self, caplog: Any) -> None:
        """Verify that the client retries on EOF error.

        We do this by checking if we correctly log.
        """
        error_to_raise = httpx.ConnectError("EOF occurred in violation of protocol")
        client = mock_httpx_client()

        # First request raises an EOF error, second request is successful
        side_effects = [error_to_raise, httpx.Response(200, json={})]
        client.send = Mock(side_effect=side_effects)  # type: ignore[method-assign]

        api_client = ApiClient(
            base_url="http://localhost:8000",
            http_client=client,
            should_verify_ssl=False,
            verify_auth=False,
            should_verify_compatibility=False,
        )

        expected_warning = "Got EOF error on /health"
        with unittest.mock.patch(
            "avatars.base_client.DEFAULT_RETRY_COUNT", 1
        ), unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_INTERVAL", 0):
            api_client.send_request(method="GET", url="/health")

        _, __, log = caplog.record_tuples[0]
        assert expected_warning in log
