from __future__ import annotations

import pytest

from prompt_toolkit.formatted_text import fragment_list_to_text
from prompt_toolkit.layout import to_window
from prompt_toolkit.widgets import Button


def button_text(button: Button) -> str:
    """Extract rendered text from a Button widget."""
    return fragment_list_to_text(
        to_window(button).content.text()
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, "<   Exit   >"),
        (
            {
                "left_symbol": "[",
                "right_symbol": "]",
            },
            "[   Exit   ]",
        ),
    ],
)
def test_button_rendering(
    kwargs: dict[str, str],
    expected: str,
) -> None:
    button = Button("Exit", **kwargs)

    assert button_text(button) == expected
