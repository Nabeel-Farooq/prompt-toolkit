"""
Tools for running functions above the current application or prompt
inside the terminal.
"""

from __future__ import annotations

from asyncio import Future, ensure_future
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from prompt_toolkit.eventloop import run_in_executor_with_context

from .current import get_app_or_none

__all__ = [
    "run_in_terminal",
    "in_terminal",
]

_T = TypeVar("_T")


def run_in_terminal(
    func: Callable[[], _T],
    render_cli_done: bool = False,
    in_executor: bool = False,
) -> Awaitable[_T]:
    """
    Run a synchronous function above the current application or prompt.

    The prompt/application is temporarily hidden, allowing safe terminal
    output. After execution, the interface is restored.

    :param func:
        Callable to execute.
    :param render_cli_done:
        When `True`, render the interface in "Done" state before execution.
        Otherwise, erase the interface completely.
    :param in_executor:
        Run the function in a thread executor to avoid blocking the event loop.
    :returns:
        Awaitable future containing the function result.
    """

    async def run() -> _T:
        async with in_terminal(render_cli_done=render_cli_done):
            if in_executor:
                return await run_in_executor_with_context(func)

            return func()

    return ensure_future(run())


@asynccontextmanager
async def in_terminal(
    render_cli_done: bool = False,
) -> AsyncGenerator[None, None]:
    """
    Suspend the current application and execute code directly in the terminal.

    Example::

        async def f():
            async with in_terminal():
                call_some_function()
                await call_some_async_function()
    """
    app = get_app_or_none()

    if app is None or not app._is_running:
        yield
        return

    # Ensure nested/queued `run_in_terminal` calls execute sequentially.
    previous_run_in_terminal_f = app._running_in_terminal_f

    new_run_in_terminal_f: Future[None] = Future()
    app._running_in_terminal_f = new_run_in_terminal_f

    # Wait for previous terminal execution to finish.
    if previous_run_in_terminal_f is not None:
        await previous_run_in_terminal_f

    # Wait for CPR responses before detaching input.
    # Otherwise terminal escape sequences may leak to stdout.
    if app.output.responds_to_cpr:
        await app.renderer.wait_for_cpr_responses()

    # Render completed UI state or clear the interface.
    if render_cli_done:
        app._redraw(render_as_done=True)
    else:
        app.renderer.erase()

    app._running_in_terminal = True

    try:
        # Temporarily detach prompt-toolkit input handling.
        with app.input.detach(), app.input.cooked_mode():
            yield

    finally:
        try:
            app._running_in_terminal = False

            # Restore renderer/application state.
            app.renderer.reset()
            app._request_absolute_cursor_position()
            app._redraw()

        finally:
            # Future may already be cancelled externally.
            if not new_run_in_terminal_f.done():
                new_run_in_terminal_f.set_result(None)
