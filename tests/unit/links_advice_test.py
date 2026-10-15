from avatar_yaml.models.schema import LinkMethod

from avatars.links_advice import (
    AdvisedLink,
    TablesLinksAdvice,
    UnlinkedForeignKey,
    parse_tables_links_advice,
)


def test_parse_reads_the_links_of_each_parent_and_the_unlinked_foreign_keys() -> None:
    results = [
        {
            "table_name": "doctor",
            "advice": {
                "links": [
                    {
                        "field": "id",
                        "to": {"table": "visit", "field": "doctor_id"},
                        "method": "linear_sum_assignment",
                        "confidence": "high",
                    }
                ],
                "unlinked_foreign_keys": [],
            },
        },
        [
            {
                "table_name": "visit",
                "advice": {
                    "links": [],
                    "unlinked_foreign_keys": [
                        {"field": "nurse", "candidate_tables": ["doctor", "patient"]}
                    ],
                },
            }
        ],
    ]

    advice = parse_tables_links_advice(results)

    assert advice == TablesLinksAdvice(
        links=[
            AdvisedLink(
                parent_table="doctor",
                parent_field="id",
                child_table="visit",
                child_field="doctor_id",
                method=LinkMethod.LINEAR_SUM_ASSIGNMENT,
                confidence="high",
            )
        ],
        unlinked_foreign_keys=[
            UnlinkedForeignKey(
                table="visit", field="nurse", candidate_tables=["doctor", "patient"]
            )
        ],
    )


def test_parse_an_advice_without_the_links_fields_gives_no_link() -> None:
    advice = parse_tables_links_advice([{"table_name": "t", "advice": {"k": 20}}])

    assert advice == TablesLinksAdvice()
