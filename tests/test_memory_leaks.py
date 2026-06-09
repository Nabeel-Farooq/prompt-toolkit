from __future__ import annotations

import gc

from prompt_toolkit.shortcuts.prompt import PromptSession


def count_prompt_session_instances() -> int:
    """Return the number of live PromptSession instances."""
    gc.collect()

    return sum(
        1
        for obj in gc.get_objects()
        if isinstance(obj, PromptSession)
    )


def test_prompt_session_memory_leak() -> None:
    initial_count = count_prompt_session_instances()

    session = PromptSession()

    assert (
        count_prompt_session_instances()
        >= initial_count + 1
    )

    del session

    assert (
        count_prompt_session_instances()
        <= initial_count
    )
