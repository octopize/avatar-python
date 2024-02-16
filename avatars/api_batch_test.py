from unittest.mock import Mock
from uuid import uuid4

import pandas as pd
import pytest

from avatars.api import download_sensitive_unshuffled_avatar_dataframe_from_batch
from avatars.models import (
    AvatarizationBatchResult,
    AvatarizationPerBatchResult,
    Dataset,
    FileType,
)


@pytest.fixture
def batch_result() -> AvatarizationBatchResult:
    batch = AvatarizationBatchResult(
        training_result=AvatarizationPerBatchResult(
            avatars_dataset=Dataset(
                id=uuid4(),
                hash="plouf",
                download_url="truc",
                nb_dimensions=1,
                filetype=FileType.csv,
            ),
            sensitive_unshuffled_avatars_datasets=Dataset(
                id=uuid4(),
                hash="plouf",
                download_url="truc",
                nb_dimensions=1,
                filetype=FileType.csv,
            ),
            original_id=uuid4(),
        ),
        batch_results=[
            AvatarizationPerBatchResult(
                avatars_dataset=Dataset(
                    id=uuid4(),
                    hash="plouf",
                    download_url="truc",
                    nb_dimensions=1,
                    filetype=FileType.csv,
                ),
                sensitive_unshuffled_avatars_datasets=Dataset(
                    id=uuid4(),
                    hash="plouf",
                    download_url="truc",
                    nb_dimensions=1,
                    filetype=FileType.csv,
                ),
                original_id=uuid4(),
            )
        ],
    )
    return batch


def test_get_sensitive_unshuffled_avatar_from_batch(
    batch_result: AvatarizationBatchResult,
) -> None:
    train = pd.DataFrame(
        data={
            "a": [1, 3],
            "b": ["a", "b"],
        }
    )
    split = pd.DataFrame(
        data={
            "a": [4, 2],
            "b": ["a", "b"],
        }
    )

    order = {
        batch_result.training_result.original_id: pd.Index([0, 2]),
        batch_result.batch_results[0].original_id: pd.Index([3, 1]),
    }

    client = Mock()
    # this is mocking the two first calls to the function download_dataframe
    client.pandas_integration.download_dataframe.side_effect = [train, split]
    result = download_sensitive_unshuffled_avatar_dataframe_from_batch(
        client=client,
        avatarization_batch_result=batch_result,
        order=order,
    )
    expected = pd.DataFrame(
        data={
            "a": [1, 2, 3, 4],
            "b": ["a", "b", "b", "a"],
        }
    )

    pd.testing.assert_frame_equal(result, expected)
