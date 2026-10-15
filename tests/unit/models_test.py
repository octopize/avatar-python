from typing import Any

import pytest

from avatars.models import MeUser


def _me_payload(**environment: Any) -> dict[str, Any]:
    return {
        "id": "decade00-0000-4000-a000-000000000000",
        "organization_id": "decade00-0000-4000-a000-000000000000",
        "email": "user@example.com",
        "role": "user",
        "environment": {
            "dataset_expiration_days": 30,
            "max_allowed_dimensions_per_dataset": 100,
            "max_allowed_lines_per_dataset": 10_000,
            **environment,
        },
    }


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        pytest.param({}, None, id="api-without-license-type"),
        pytest.param({"license_type": None}, None, id="null"),
        pytest.param({"license_type": "free_trial"}, "free_trial", id="known-value"),
        pytest.param({"license_type": "new_tier"}, "new_tier", id="unknown-value"),
        pytest.param(
            {"license_type": "free_trial", "new_field": 1}, "free_trial", id="unknown-field"
        ),
    ],
)
def test_me_user_accepts_the_responses_of_other_api_versions(
    environment: dict[str, Any], expected: str | None
) -> None:
    me = MeUser.model_validate(_me_payload(**environment))

    assert me.environment.license_type == expected
