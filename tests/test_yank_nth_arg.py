from __future__ import annotations

import pytest

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.history import InMemoryHistory


HISTORY_ENTRY_1 = "alpha beta gamma delta"
HISTORY_ENTRY_2 = "one two three four"


@pytest.fixture
def history() -> InMemoryHistory:
    """Create prefilled history for testing."""
    history = InMemoryHistory()
    history.append_string(HISTORY_ENTRY_1)
    history.append_string(HISTORY_ENTRY_2)
    return history


# ============================================================================
# yank_last_arg
# ============================================================================


def test_empty_history() -> None:
    buffer = Buffer()

    buffer.yank_last_arg()

    assert buffer.document.current_line == ""


def test_simple_search(history: InMemoryHistory) -> None:
    buffer = Buffer(history=history)

    buffer.yank_last_arg()

    assert buffer.document.current_line == "four"


def test_simple_search_with_quotes(history: InMemoryHistory) -> None:
    history.append_string("""one two "three 'x' four"\n""")

    buffer = Buffer(history=history)
    buffer.yank_last_arg()

    assert buffer.document.current_line == '''"three 'x' four"'''


def test_simple_search_with_arg(history: InMemoryHistory) -> None:
    buffer = Buffer(history=history)

    buffer.yank_last_arg(n=2)

    assert buffer.document.current_line == "three"


def test_simple_search_with_arg_out_of_bounds(
    history: InMemoryHistory,
) -> None:
    buffer = Buffer(history=history)

    buffer.yank_last_arg(n=8)

    assert buffer.document.current_line == ""


def test_repeated_search(history: InMemoryHistory) -> None:
    buffer = Buffer(history=history)

    buffer.yank_last_arg()
    buffer.yank_last_arg()

    assert buffer.document.current_line == "delta"


def test_repeated_search_with_wraparound(
    history: InMemoryHistory,
) -> None:
    buffer = Buffer(history=history)

    buffer.yank_last_arg()
    buffer.yank_last_arg()
    buffer.yank_last_arg()

    assert buffer.document.current_line == "four"


# ============================================================================
# yank_nth_arg
# ============================================================================


def test_yank_nth_arg(history: InMemoryHistory) -> None:
    buffer = Buffer(history=history)

    buffer.yank_nth_arg()

    assert buffer.document.current_line == "two"


def test_repeated_yank_nth_arg(history: InMemoryHistory) -> None:
    buffer = Buffer(history=history)

    buffer.yank_nth_arg()
    buffer.yank_nth_arg()

    assert buffer.document.current_line == "beta"


def test_yank_nth_arg_with_arg(history: InMemoryHistory) -> None:
    buffer = Buffer(history=history)

    buffer.yank_nth_arg(n=2)

    assert buffer.document.current_line == "three"
