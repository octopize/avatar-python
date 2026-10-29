"""The generated client and the protocol the SDK codes against must not drift.

``avatars.sdk_client`` carries a compile-time assertion that ``ApiClient`` satisfies
``SdkClient``, and mypy is the primary gate. These tests are the runtime backstop:
they catch the drift mypy waives -- a parameter renamed while staying positionally
compatible, or a method that disappears from a resource class that is itself still
structurally acceptable.

When one of these fails after ``just generate-python``, the fix is to update
``sdk_client.py`` to match the new generated signature (and then the serverless
client to match it too) -- never to loosen the assertion.
"""

import inspect

import pytest

from avatars.client import ApiClient
from avatars.sdk_client import (
    CompatibilityApi,
    HealthApi,
    JobsApi,
    ResourcesApi,
    ResultsApi,
    SdkClient,
    UsersApi,
)
from tests.unit.conftest import api_client_factory

# Each sub-protocol and the attribute on the client that must implement it.
SUB_APIS: list[tuple[str, type]] = [
    ("resources", ResourcesApi),
    ("jobs", JobsApi),
    ("results", ResultsApi),
    ("users", UsersApi),
    ("health", HealthApi),
    ("compatibility", CompatibilityApi),
]

# Members of SdkClient itself that are not one of the sub-APIs above.
TOP_LEVEL_MEMBERS = [
    "base_url",
    "should_verify_ssl",
    "upload_file",
    "download_file",
    "list_input_files",
    "is_using_api_key",
    "send_request",
]


@pytest.fixture
def client() -> ApiClient:
    """A real ApiClient, built the way the existing unit tests build one.

    It must go through ``__init__`` rather than be constructed bare: the resource
    attributes the protocol requires are assigned there, not declared on the class.
    """
    return api_client_factory()


def _protocol_members(protocol: type) -> list[str]:
    return sorted(m for m in protocol.__protocol_attrs__ if not m.startswith("_"))  # type: ignore[attr-defined]


@pytest.mark.parametrize(("attribute", "protocol"), SUB_APIS, ids=[a for a, _ in SUB_APIS])
def test_generated_client_exposes_each_sub_api(
    client: ApiClient, attribute: str, protocol: type
) -> None:
    assert hasattr(client, attribute), (
        f"ApiClient no longer exposes '{attribute}'. Either the schema dropped the tag "
        f"or the SDK should stop depending on it."
    )
    assert isinstance(getattr(client, attribute), protocol)


@pytest.mark.parametrize(("attribute", "protocol"), SUB_APIS, ids=[a for a, _ in SUB_APIS])
def test_sub_api_signatures_match(client: ApiClient, attribute: str, protocol: type) -> None:
    """Every method the SDK calls exists on the generated class with the same parameters."""
    implementation = getattr(client, attribute)

    for member in _protocol_members(protocol):
        declared = getattr(protocol, member)
        actual = getattr(implementation, member, None)
        assert actual is not None, (
            f"ApiClient.{attribute} has no '{member}'; regeneration dropped a method "
            f"the SDK calls."
        )

        # The protocol declares what the SDK passes. The generated method may take
        # more (it takes a `timeout` the SDK never uses), but every extra has to be
        # optional, and the shared parameters have to line up in the same order --
        # otherwise a positional call made through the protocol lands on the wrong
        # argument.
        expected = [p for p in inspect.signature(declared).parameters if p != "self"]
        actual = inspect.signature(actual).parameters

        assert expected == list(actual)[: len(expected)], (
            f"ApiClient.{attribute}.{member} signature drifted.\n"
            f"  sdk_client.py declares: {expected}\n"
            f"  api.py now has:         {list(actual)}"
        )

        required_extras = [
            name
            for name, param in list(actual.items())[len(expected) :]
            if param.default is inspect.Parameter.empty
            and param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        assert not required_extras, (
            f"ApiClient.{attribute}.{member} gained required parameter(s) "
            f"{required_extras} that the SDK does not pass."
        )


def test_generated_client_exposes_top_level_members(client: ApiClient) -> None:
    missing = [m for m in TOP_LEVEL_MEMBERS if not hasattr(client, m)]
    assert not missing, f"ApiClient is missing {missing}, which the SDK calls directly."


def test_protocol_covers_every_member_the_tests_enumerate() -> None:
    """Guard against a member being added to SdkClient and not checked here."""
    enumerated = {a for a, _ in SUB_APIS} | set(TOP_LEVEL_MEMBERS)
    declared = set(_protocol_members(SdkClient))
    assert declared == enumerated, (
        f"SdkClient members not covered by this test: {sorted(declared - enumerated)}; "
        f"listed here but absent from the protocol: {sorted(enumerated - declared)}"
    )


def test_runtime_isinstance_check(client: ApiClient) -> None:
    """``SdkClient`` is runtime_checkable, so this is a cheap smoke assertion."""
    assert isinstance(client, SdkClient)
