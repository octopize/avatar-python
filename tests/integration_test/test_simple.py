import os

import pandas as pd
import structlog

from avatars.manager import Manager
from avatars.models import JobKind

logger = structlog.get_logger(__name__)


def test_main(
    base_api_url: str = os.getenv("AVATAR_BASE_API_URL", ""),
    username: str = os.getenv("AVATAR_USERNAME", ""),
    password: str = os.getenv("AVATAR_PASSWORD", ""),
    dataset_path: str = "tests/fixtures/iris.csv",
) -> int:
    print(username, password, base_api_url)
    print(os.getenv("STORAGE_ENDPOINT_URL", ""))
    logger.info("Running main test")
    manager = Manager(base_url=base_api_url)
    manager.authenticate(username, password)

    df = pd.read_csv(dataset_path)
    runner = manager.create_runner()
    runner.add_table("iris", data=df)

    runner.set_parameters("iris", k=5)
    runner.run()
    runner.get_all_results()
    assert runner.get_status(JobKind.standard) == "finished"
    assert runner.get_status(JobKind.privacy_metrics) == "finished"
    assert runner.get_status(JobKind.signal_metrics) == "finished"

    logger.info("Done")
    return 0
