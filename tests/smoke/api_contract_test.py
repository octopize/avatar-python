"""The client/API round trip, run against a live API by services-api-ci.

Unit tests on either side cannot catch a disagreement about the wire: the API
had to stop accepting the very URL form `/results` hands out (#6532) before
anyone noticed, because nothing exercised both sides at once on an API change.

This is deliberately the shortest path that still crosses every seam a real
run crosses — upload to object storage, a job, and a download back:

    add_table   -> GET /upload_url, GET /access, PutObject
    run         -> POST /jobs
    shuffled    -> GET /results/{job}, GET /access, GetObject

`/access` is the one both directions share, and object storage is where a
misconfigured SSE-S3 key surfaces. Only the standard job runs: the metrics and
report jobs cross no seam this does not already cover, and the report needs a
binary the API CI job has no reason to install.
"""

import os
from pathlib import Path

import pandas as pd
import pytest

from avatars.manager import Manager
from avatars.models import JobKind

FIXTURES = Path(__file__).parents[2] / "fixtures"
IRIS_ROWS = 150


# Not collected by a bare `pytest` — see testpaths in pyproject.toml. Running
# this directory at all means asserting there is an API behind
# AVATAR_BASE_API_URL, so a missing key or a closed port is a failure, never a
# skip: a green run has to mean the round trip actually happened.
@pytest.fixture(scope="module")
def manager() -> Manager:
    api_key = os.environ.get("AVATAR_API_KEY")
    if not api_key:
        pytest.fail("AVATAR_API_KEY is required to run the round trip")
    return Manager(api_key=api_key)


def test_the_api_is_reachable(manager: Manager) -> None:
    manager.auth_client.health.get_health()


def test_a_table_survives_the_round_trip(manager: Manager) -> None:
    """Upload a table, avatarize it, and read the avatars back."""
    runner = manager.create_runner(set_name="ci-smoke")
    runner.add_table("iris", str(FIXTURES / "iris.csv"))
    runner.set_parameters("iris", k=5)

    runner.run(jobs_to_run=[JobKind.standard])

    shuffled = runner.shuffled("iris")

    assert isinstance(shuffled, pd.DataFrame)
    assert len(shuffled) == IRIS_ROWS
    assert set(shuffled.columns) == set(pd.read_csv(FIXTURES / "iris.csv").columns)
