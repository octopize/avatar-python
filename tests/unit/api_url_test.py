"""Tests for the error raised when the configured URL does not serve the API."""

import functools
import os
from unittest.mock import patch

import httpx
import pytest

from avatars.base_client import ApiConnectionError
from avatars.client import ApiClient
from avatars.client_config import ClientConfig
from avatars.manager import Manager
from tests.unit.conftest import FAKE_API_KEY, RequestHandle, mock_httpx_client


def _manager_answering(response: httpx.Response) -> Manager:
    handler: RequestHandle = lambda _: response  # noqa: E731
    api_client = ApiClient(
        base_url="https://avatar.company.co/api",
        http_client=mock_httpx_client(handler),
        api_key=FAKE_API_KEY,
    )
    return Manager(api_client=api_client)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"detail": "Not Found"}),
        httpx.Response(308, headers={"location": "https://avatar.company.co/api"}),
    ],
)
def test_error_gives_the_production_url(response: httpx.Response) -> None:
    with pytest.raises(ApiConnectionError) as excinfo:
        _manager_answering(response)

    assert str(excinfo.value) == (
        f"https://avatar.company.co does not serve the Avatar API "
        f"(HTTP {response.status_code}). The Octopize SaaS platform is at "
        "https://www.octopize.app. Your tenant might be at another address."
    )


def _redirect_to(location: str | None, received: list[httpx.Request]) -> RequestHandle:
    headers = {} if location is None else {"location": location}

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(308, headers=headers)

    return handler


def _manager_redirected(
    api_url: str, location: str | None, received: list[httpx.Request]
) -> Manager:
    api_client = ApiClient(
        config=ClientConfig(base_api_url=api_url, api_key=FAKE_API_KEY),
        http_client=mock_httpx_client(_redirect_to(location, received), base_url=api_url),
    )
    return Manager(api_client=api_client)


_HTTPS_MESSAGE = (
    "http://avatar.example.com redirects to HTTPS. "
    "Use base_url='https://avatar.example.com'. "
    "Requests over http:// send your API key without encryption."
)


@pytest.mark.parametrize(
    ("api_url", "location"),
    [
        ("http://avatar.example.com/api", "https://avatar.example.com/api/check_client"),
        ("http://avatar.example.com/api", "https://avatar.example.com:443/api/check_client"),
        ("http://avatar.example.com:80/api", "https://avatar.example.com/api/check_client"),
        ("http://avatar.example.com/api/", "https://avatar.example.com/api/check_client"),
    ],
)
def test_http_to_https_redirect_gives_the_https_base_url(api_url: str, location: str) -> None:
    received: list[httpx.Request] = []

    with pytest.raises(ApiConnectionError) as excinfo:
        _manager_redirected(api_url, location, received)

    assert str(excinfo.value) == _HTTPS_MESSAGE
    assert len(received) == 1


def test_default_http_client_does_not_follow_redirects() -> None:
    received: list[httpx.Request] = []
    transport = httpx.MockTransport(
        _redirect_to("https://avatar.example.com/api/check_client", received)
    )
    client_with_transport = functools.partial(httpx.Client, transport=transport)

    with (
        patch.dict(os.environ, clear=True),
        patch("avatars.base_client.httpx.Client", client_with_transport),
        pytest.raises(ApiConnectionError) as excinfo,
    ):
        Manager(base_url="http://avatar.example.com", api_key=FAKE_API_KEY)

    assert str(excinfo.value) == _HTTPS_MESSAGE
    assert len(received) == 1


@pytest.mark.parametrize(
    ("base_url", "location"),
    [
        ("http://avatar.example.com", "https://other.example.com/api/check_client"),
        ("http://avatar.example.com", "http://avatar.example.com/landing"),
        ("http://avatar.example.com", None),
        ("http://avatar.example.com:8080", "https://avatar.example.com:8443/api"),
        ("http://avatar.example.com:8080", "https://avatar.example.com/api"),
        ("http://avatar.example.com", "https://avatar.example.com:8443/api"),
        ("https://avatar.example.com", "https://avatar.example.com/landing"),
        ("https://avatar.example.com", "https://www.example.com/"),
    ],
)
def test_other_redirect_gives_the_production_url(base_url: str, location: str | None) -> None:
    received: list[httpx.Request] = []

    with pytest.raises(ApiConnectionError) as excinfo:
        _manager_redirected(f"{base_url}/api", location, received)

    assert str(excinfo.value) == (
        f"{base_url} does not serve the Avatar API (HTTP 308). The Octopize SaaS "
        "platform is at https://www.octopize.app. Your tenant might be at another address."
    )
    assert len(received) == 1
