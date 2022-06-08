import os

from avatars.client import ApiClient
from avatars.models import (
    ColumnDetail,
    ColumnType,
    DatasetResponse,
    JobCreate,
    JobParameters,
    PatchDataset,
)


def main():
    client = ApiClient(
        base_url=os.environ["AVATAR_BASE_URL"],
    )

    client.authenticate(
        username=os.environ["AVATAR_USER"], password=os.environ["AVATAR_PASSWORD"]
    )

    # Let's verify that we can connect to the API server
    client.health.get_health()

    # All calls to Dataset
    response = client.datasets.create_dataset(
        request=open("../../../core/fixtures/iris.csv", "rb")
    )
    dataset_id = response.id
    print(response, "\n")
    response = client.datasets.get_dataset(id=dataset_id)
    print(response, "\n")
    response = client.datasets.patch_dataset(
        id=dataset_id,
        request=PatchDataset(
            columns=[ColumnDetail(type=ColumnType.int, label="sepal.width")]
        ),
    )
    print(response, "\n")
    response = client.datasets.analyze_dataset(id=dataset_id)
    print(response, "\n")
    response = client.datasets.get_dataset_correlations(id=dataset_id)
    print(response, "\n")
    response = client.datasets.download_dataset(id=dataset_id)
    print(response, "\n")

    # All calls to Health
    response = client.health.get_health()
    print(response, "\n")
    response = client.health.get_health_task()
    print(response, "\n")
    response = client.health.get_health_db()
    print(response, "\n")

    # All calls to Jobs
    job_create = JobCreate(dataset_id=dataset_id, parameters=JobParameters(k=20))
    response = client.jobs.create_job(request=job_create)
    print(response, "\n")
    job_id = response.id
    response = client.jobs.get_job(id=job_id)
    print(response, "\n")

    # All calls to Metrics
    response = client.metrics.get_job_projections(job_id=job_id)
    print(response, "\n")
    response = client.metrics.get_variable_contributions(
        job_id=job_id, dataset_id=dataset_id
    )
    print(response, "\n")
    response = client.metrics.get_explained_variance(job_id=job_id)
    print(response, "\n")

    # All calls to Users
    response = client.users.find_users()
    print(response, "\n")
    response = client.users.get_user(username="user_integration")
    print(response, "\n")


if __name__ == "__main__":
    main()
