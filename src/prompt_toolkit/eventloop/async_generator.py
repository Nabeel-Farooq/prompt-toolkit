"""
Utilities for working with asynchronous generators.
"""

from __future__ import annotations

from asyncio import get_running_loop
from collections.abc import AsyncGenerator, Callable, Iterable
from contextlib import asynccontextmanager
from queue import Empty, Full, Queue
from typing import Any, TypeVar

from .utils import run_in_executor_with_context

__all__ = [
    "aclosing",
    "generator_to_async_generator",
]

_T_Generator = TypeVar("_T_Generator", bound=AsyncGenerator[Any, None])
_T = TypeVar("_T")


@asynccontextmanager
async def aclosing(
    thing: _T_Generator,
) -> AsyncGenerator[_T_Generator, None]:
    """
    Async equivalent of `contextlib.closing`.

    Ensures the async generator is properly closed when exiting
    the context manager.
    """
    try:
        yield thing
    finally:
        await thing.aclose()


# Default queue size chosen to balance:
# - throughput
# - memory usage
# - back-pressure between producer/consumer
#
# Small buffers significantly reduce performance for large result sets,
# while unbounded buffers can waste memory and CPU on unused items.
DEFAULT_BUFFER_SIZE: int = 1000


class _Done:
    """
    Sentinel object used to indicate completion.
    """

    __slots__ = ()


async def generator_to_async_generator(
    get_iterable: Callable[[], Iterable[_T]],
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> AsyncGenerator[_T, None]:
    """
    Convert a synchronous iterable/generator into an async generator.

    The iterable is consumed in a background thread while items are passed
    through a bounded queue to provide back-pressure.

    :param get_iterable:
        Callable returning a synchronous iterable or generator.
    :param buffer_size:
        Queue size between producer and async consumer.
    """
    if buffer_size < 1:
        raise ValueError("buffer_size must be at least 1.")

    quitting = False

    # Bounded queue to avoid excessive memory usage.
    q: Queue[_T | _Done] = Queue(maxsize=buffer_size)

    loop = get_running_loop()

    def safe_put(item: _T | _Done) -> bool:
        """
        Put an item into the queue while respecting cancellation.
        """
        while True:
            try:
                q.put(item, timeout=1)
                return True

            except Full:
                if quitting:
                    return False

    def runner() -> None:
        """
        Consume the iterable in a background thread and push items
        into the queue.
        """
        try:
            for item in get_iterable():
                if quitting:
                    return

                if not safe_put(item):
                    return

        finally:
            safe_put(_Done())

    # Start producer thread.
    runner_f = run_in_executor_with_context(runner)

    try:
        while True:
            try:
                item = q.get_nowait()

            except Empty:
                item = await loop.run_in_executor(None, q.get)

            if isinstance(item, _Done):
                break

            yield item

    finally:
        # Stop producer thread when async generator closes early.
        quitting = True

        # Ensure background thread exits cleanly.
        await runner_f
