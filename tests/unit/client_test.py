import unittest
from typing import Any, Type
from unittest.mock import Mock, patch

import httpx
import pytest

from avatars.base_client import TimeoutError
from avatars.client import ApiClient
from tests.unit.conftest import RequestHandle, api_client_factory, mock_httpx_client


@patch("httpx.Client")
def test_should_verify_ssl(mock_client: Any) -> None:
    base_url = "https://test.com"

    def do_request(api_client: ApiClient, **kwargs: Any) -> None:
        api_client.request("GET", base_url, **kwargs)

    # Verify default is set to True
    api_client = ApiClient(base_url=base_url, verify_auth=False)
    do_request(api_client)
    assert mock_client.call_args.kwargs["verify"] is True
    mock_client.reset_mock()

    # Verify that the should_verify_ssl parameter is passed to the httpx.Client
    api_client = ApiClient(
        base_url=base_url,
        should_verify_ssl=False,
        verify_auth=False,
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


def prepare_api_client_for(resp: httpx.Response) -> ApiClient:
    client = mock_httpx_client()
    client.send = Mock(return_value=resp)  # type: ignore[method-assign]

    return ApiClient(
        base_url="http://localhost:8000",
        http_client=client,
        should_verify_ssl=False,
        verify_auth=False,
    )


class TestClientRequest:
    @pytest.fixture(scope="session")
    def json_ok_response(self) -> RequestHandle:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"message": "ok"})

        return handler

    def test_can_handle_standard_json_ok_response(self, json_ok_response: RequestHandle) -> None:
        api_client = api_client_factory(json_ok_response)

        result = api_client.request("GET", "/health")

        assert result == {"message": "ok"}

    def test_retries_on_ssl_eof_error(self, caplog: Any) -> None:
        """Verify that the client retries on httpx.RequestError.

        We do this by checking if we correctly log.
        """
        error_message = "error=EOF occurred in violation of protocol"
        error_to_raise = httpx.RequestError(error_message)
        client = mock_httpx_client()

        # First request raises an EOF error, second request is successful
        side_effects = [error_to_raise, httpx.Response(200, json={"message": "ok"})]
        client.send = Mock(side_effect=side_effects)  # type: ignore[method-assign]

        api_client = ApiClient(
            base_url="http://localhost:8000",
            http_client=client,
            should_verify_ssl=False,
            verify_auth=False,
        )

        with (
            unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_COUNT", 1),
            unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_INTERVAL", 0.1),
        ):
            response = api_client.send_request(method="GET", url="/health")

        _, __, log = caplog.record_tuples[0]
        assert error_message in log
        assert "/health" in log

        assert response == {"message": "ok"}

    def test_json_unrecognized_error(self, caplog: Any) -> None:
        """Verify that the client handles error in JSON format with unrecognized structure."""
        api_client = prepare_api_client_for(httpx.Response(403, json={"whatever": "a json error"}))

        with pytest.raises(Exception) as exc_info:
            api_client.send_request(method="GET", url="/health")

        assert exc_info.type is Exception
        msg = exc_info.value.args[0]
        assert "Got error in HTTP request" in msg
        assert "Error status 403 - Internal error: {'whatever': 'a json error'}" in msg

    def test_json_error(self, caplog: Any) -> None:
        """Verify that the client handles error in JSON format."""
        api_client = prepare_api_client_for(
            httpx.Response(403, json={"message": "a json error in message"})
        )

        with pytest.raises(Exception) as exc_info:
            api_client.send_request(method="GET", url="/health")

        assert exc_info.type is Exception
        msg = exc_info.value.args[0]
        assert "Got error in HTTP request" in msg
        assert "Error status 403 - a json error in message" in msg

    def test_non_json_error(self, caplog: Any) -> None:
        """Verify that the client handles error not in JSON format."""
        api_client = prepare_api_client_for(httpx.Response(403, text="a plain text error"))

        with pytest.raises(Exception) as exc_info:
            api_client.send_request(method="GET", url="/health")

        assert exc_info.type is Exception
        msg = exc_info.value.args[0]
        assert "Got error in HTTP request" in msg
        assert "Error status 403" in msg
        assert "a plain text error" in msg

    @pytest.mark.parametrize("exc_cls", [httpx.ReadTimeout, httpx.WriteTimeout])
    def test_reraise_timeout_as_custom_timeout(self, exc_cls: Type[Exception]) -> None:
        """Verify that we reraise a custom error on timeout after the last retrying attempt."""
        error_to_raise = exc_cls("whatever")
        client = mock_httpx_client()

        # First call raises a timeout, gets retried, then a second timeout is raised
        side_effects = [error_to_raise, error_to_raise]

        client.send = Mock(side_effect=side_effects)  # type: ignore[method-assign]

        api_client = ApiClient(
            base_url="http://localhost:8000",
            http_client=client,
            should_verify_ssl=False,
            verify_auth=False,
        )
        with (
            unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_COUNT", 1),
            unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_INTERVAL", 0.1),
            pytest.raises(TimeoutError, match="Timeout waiting for GET on /health"),
        ):
            api_client.send_request(method="GET", url="/health")

    def test_reraise_same_error_at_end_of_retry(self) -> None:
        """Verify that we reraise the same error at the end of the retrying attempts."""
        error_to_raise = httpx.RequestError("whatever")
        client = mock_httpx_client()

        # First call raises an error, gets retried, then a second error is raised, but not retried.
        side_effects = [error_to_raise, error_to_raise]

        client.send = Mock(side_effect=side_effects)  # type: ignore[method-assign]

        api_client = ApiClient(
            base_url="http://localhost:8000",
            http_client=client,
            should_verify_ssl=False,
            verify_auth=False,
        )
        with (
            unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_COUNT", 1),
            unittest.mock.patch("avatars.base_client.DEFAULT_RETRY_INTERVAL", 0.1),
            pytest.raises(httpx.RequestError, match="whatever"),
        ):
            api_client.send_request(method="GET", url="/health")
