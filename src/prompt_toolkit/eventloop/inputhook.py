"""
Asyncio input hook integration similar to Python's `PyOS_InputHook`.

This module allows another event loop (Qt, GTK, Tkinter, etc.) to run while
the asyncio selector waits for I/O readiness.

The custom selector delegates waiting to the external event loop until the
main selector becomes ready again.

The input hook must return when prompt-toolkit regains control. This can be
detected by:

- Periodically calling `input_is_ready()`
- Watching the provided file descriptor for readability
"""

from __future__ import annotations

import asyncio
import os
import select
import selectors
import sys
import threading
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import Callable, Mapping
from selectors import BaseSelector, SelectorKey
from typing import TYPE_CHECKING, Any

__all__ = [
    "new_eventloop_with_inputhook",
    "set_eventloop_with_inputhook",
    "InputHookSelector",
    "InputHookContext",
    "InputHook",
]

if TYPE_CHECKING:
    from typing import TypeAlias

    from _typeshed import FileDescriptorLike

    _EventMask = int


class InputHookContext:
    """
    Context object passed to the input hook.
    """

    __slots__ = ("_fileno", "input_is_ready")

    def __init__(
        self,
        fileno: int,
        input_is_ready: Callable[[], bool],
    ) -> None:
        self._fileno = fileno
        self.input_is_ready = input_is_ready

    def fileno(self) -> int:
        """
        Return the file descriptor to monitor.
        """
        return self._fileno


InputHook: TypeAlias = Callable[[InputHookContext], None]


def new_eventloop_with_inputhook(
    inputhook: Callable[[InputHookContext], None],
) -> AbstractEventLoop:
    """
    Create a new asyncio event loop with an integrated input hook.
    """
    selector = InputHookSelector(
        selectors.DefaultSelector(),
        inputhook,
    )

    return asyncio.SelectorEventLoop(selector)


def set_eventloop_with_inputhook(
    inputhook: Callable[[InputHookContext], None],
) -> AbstractEventLoop:
    """
    Create and activate a new event loop using the given input hook.

    Deprecated helper maintained for backwards compatibility.
    """
    loop = new_eventloop_with_inputhook(inputhook)

    asyncio.set_event_loop(loop)

    return loop


class InputHookSelector(BaseSelector):
    """
    Selector wrapper that integrates an external GUI/input event loop.

    Example::

        selector = selectors.DefaultSelector()

        loop = asyncio.SelectorEventLoop(
            InputHookSelector(selector, inputhook)
        )

        asyncio.set_event_loop(loop)
    """

    def __init__(
        self,
        selector: BaseSelector,
        inputhook: Callable[[InputHookContext], None],
    ) -> None:
        self.selector = selector
        self.inputhook = inputhook

        # Pipe used to notify the input hook when the selector becomes ready.
        self._r, self._w = os.pipe()

    def register(
        self,
        fileobj: FileDescriptorLike,
        events: _EventMask,
        data: Any = None,
    ) -> SelectorKey:
        return self.selector.register(
            fileobj,
            events,
            data=data,
        )

    def unregister(self, fileobj: FileDescriptorLike) -> SelectorKey:
        return self.selector.unregister(fileobj)

    def modify(
        self,
        fileobj: FileDescriptorLike,
        events: _EventMask,
        data: Any = None,
    ) -> SelectorKey:
        return self.selector.modify(
            fileobj,
            events,
            data=data,
        )

    def select(
        self,
        timeout: float | None = None,
    ) -> list[tuple[SelectorKey, _EventMask]]:
        """
        Wait for I/O readiness while allowing another event loop to run.
        """
        loop = get_running_loop()

        # If asyncio already has ready callbacks/tasks,
        # skip the input hook entirely.
        if getattr(loop, "_ready", []):
            return self.selector.select(timeout=timeout)

        ready = False
        result: list[tuple[SelectorKey, _EventMask]] | None = None

        def run_selector() -> None:
            """
            Run the real selector in a background thread.
            """
            nonlocal ready, result

            result = self.selector.select(timeout=timeout)

            try:
                os.write(self._w, b"x")
            except OSError:
                return

            ready = True

        thread = threading.Thread(
            target=run_selector,
            daemon=True,
        )

        thread.start()

        def input_is_ready() -> bool:
            return ready

        # Let external event loop run until selector is ready.
        self.inputhook(
            InputHookContext(
                self._r,
                input_is_ready,
            )
        )

        # Flush pipe notification.
        try:
            # Required for gevent monkey patch compatibility.
            if sys.platform != "win32":
                select.select([self._r], [], [], None)

            os.read(self._r, 1024)

        except OSError:
            # Interrupted system call (e.g. SIGWINCH resize event).
            pass

        # Wait for selector thread completion.
        thread.join()

        return result or []

    def close(self) -> None:
        """
        Release resources and close wrapped selector.
        """
        if self._r >= 0:
            os.close(self._r)

        if self._w >= 0:
            os.close(self._w)

        self._r = self._w = -1

        self.selector.close()

    def get_map(self) -> Mapping[FileDescriptorLike, SelectorKey]:
        """
        Return selector registration mapping.
        """
        return self.selector.get_map()
