from __future__ import annotations

from asyncio import run
from collections.abc import Generator

from prompt_toolkit.eventloop import generator_to_async_generator


def _sync_generator() -> Generator[int, None, None]:
    yield 1
    yield 10


def test_generator_to_async_generator() -> None:
    """
    Verify that a synchronous generator can be consumed
    through an async generator interface.
    """

    async def collect_items() -> list[int]:
        return [
            item
            async for item in generator_to_async_generator(
                _sync_generator
            )
        ]

    assert run(collect_items()) == [1, 10]
