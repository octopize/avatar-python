from typing import Callable, Optional

import httpx

from avatars.client import ApiClient

RequestHandle = Callable[[httpx.Request], httpx.Response]


def mock_httpx_client(handler: Optional[RequestHandle] = None) -> httpx.Client:
    """Generate a HTTPX client with a MockTransport."""

    if handler is None:
        handler = lambda request: httpx.Response(200, json={})  # noqa: E731

    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="http://localhost:8000", transport=transport)


def api_client_factory(handler: Optional[RequestHandle] = None) -> ApiClient:
    """Generate an API client with a mock transport.

    The handler returns an empty 200 response by default.
    Consider overriding it with a custom handler for more complex tests.
    """
    http_client = mock_httpx_client(handler)
    return ApiClient(
        base_url="http://localhost:8000",
        http_client=http_client,
        verify_auth=False,
        should_verify_compatibility=False,
    )
