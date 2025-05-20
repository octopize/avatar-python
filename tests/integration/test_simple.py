import os
from uuid import uuid4

import pandas as pd
import structlog

from avatars.manager import Manager
from avatars.models import JobKind

logger = structlog.get_logger(__name__)


def test_main(
    base_api_url: str = os.getenv("AVATAR_BASE_API_URL", ""),
    username: str = os.getenv("AVATAR_USERNAME", ""),
    password: str = os.getenv("AVATAR_PASSWORD", ""),
    dataset_path: str = "fixtures/iris.csv",
) -> None:
    logger.info("Running main test")
    manager = Manager(base_url=base_api_url)
    manager.authenticate(username, password)

    df = pd.read_csv(dataset_path)

    # This filename is used to test the special characters in the filename
    filename = "iris_$*'@!?:;=[]()-_/.&+"
    runner = manager.create_runner(set_name=f"iris_{uuid4()}")
    runner.add_table(filename, data=df)

    runner.set_parameters(filename, k=5)
    runner.run()
    runner.get_all_results()
    assert runner.get_status(JobKind.standard) == "finished"
    assert runner.get_status(JobKind.privacy_metrics) == "finished"
    assert runner.get_status(JobKind.signal_metrics) == "finished"

    logger.info("Done")


def test_report_without_avat(
    base_api_url: str = os.getenv("AVATAR_BASE_API_URL", ""),
    username: str = os.getenv("AVATAR_USERNAME", ""),
    password: str = os.getenv("AVATAR_PASSWORD", ""),
    dataset_path: str = "fixtures/iris.csv",
) -> None:
    logger.info("Running main test")
    manager = Manager(base_url=base_api_url)
    manager.authenticate(username, password)

    runner = manager.create_runner(set_name="report_without_avat")
    runner.add_table("wbcd", dataset_path, avatar_data=dataset_path)
    runner.run(jobs_to_run=[JobKind.signal_metrics, JobKind.privacy_metrics, JobKind.report])
    runner.get_all_results()
    runner.download_report("report.pdf")
    assert runner.get_status(JobKind.privacy_metrics) == "finished"
    assert runner.get_status(JobKind.signal_metrics) == "finished"
    assert runner.get_status(JobKind.report) == "finished"
    os.remove("report.pdf")
    logger.info("Done")
