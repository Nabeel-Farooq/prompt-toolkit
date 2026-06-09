from __future__ import annotations

import itertools

import pytest

from prompt_toolkit.utils import take_using_weights


def take_items(generator, count: int) -> list[str]:
    """Consume a fixed number of items from a generator."""
    return list(itertools.islice(generator, count))


def test_weight_distribution() -> None:
    data = take_items(
        take_using_weights(
            ["A", "B", "C"],
            [5, 10, 20],
        ),
        35,
    )

    assert data.count("A") == 5
    assert data.count("B") == 10
    assert data.count("C") == 20


def test_weight_distribution_order() -> None:
    data = take_items(
        take_using_weights(
            ["A", "B", "C"],
            [5, 10, 20],
        ),
        35,
    )

    assert data == [
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
    ]


@pytest.mark.parametrize(
    ("weights", "count", "expected"),
    [
        ([20, 10, 5], 35, {"A": 20, "B": 10, "C": 5}),
        ([20, 10, 5], 70, {"A": 40, "B": 20, "C": 10}),
        ([-20, 10, 0], 70, {"A": 0, "B": 70, "C": 0}),
    ],
)
def test_weight_counts(
    weights: list[int],
    count: int,
    expected: dict[str, int],
) -> None:
    data = take_items(
        take_using_weights(
            ["A", "B", "C"],
            weights,
        ),
        count,
    )

    for item, expected_count in expected.items():
        assert data.count(item) == expected_count


def test_all_zero_weights_raise_value_error() -> None:
    with pytest.raises(ValueError):
        take_items(
            take_using_weights(
                ["A", "B", "C"],
                [0, 0, 0],
            ),
            70,
        )
