from __future__ import annotations

import os
import signal
import sys
import threading
from collections import deque
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager
from typing import Generic, TypeVar

from wcwidth import wcwidth

__all__ = [
    "Event",
    "DummyContext",
    "get_cwidth",
    "suspend_to_background_supported",
    "is_conemu_ansi",
    "is_windows",
    "in_main_thread",
    "get_bell_environment_variable",
    "get_term_environment_variable",
    "take_using_weights",
    "to_str",
    "to_int",
    "AnyFloat",
    "to_float",
    "is_dumb_terminal",
]

# Used to ensure sphinx autodoc does not try to import platform-specific
# stuff when documenting win32.py modules.
SPHINX_AUTODOC_RUNNING = "sphinx.ext.autodoc" in sys.modules

_Sender = TypeVar("_Sender", covariant=True)
_T = TypeVar("_T")


class Event(Generic[_Sender]):
    """
    Simple event to which event handlers can be attached. For instance::

        class Cls:
            def __init__(self):
                self.event = Event(self)

        obj = Cls()

        def handler(sender):
            pass

        obj.event += handler
        obj.event()
    """

    __slots__ = ("sender", "_handlers")

    def __init__(
        self,
        sender: _Sender,
        handler: Callable[[_Sender], None] | None = None,
    ) -> None:
        self.sender = sender
        self._handlers: list[Callable[[_Sender], None]] = []

        if handler is not None:
            self += handler

    def __call__(self) -> None:
        """Fire event."""
        for handler in self._handlers:
            handler(self.sender)

    def fire(self) -> None:
        """Alias for just calling the event."""
        self()

    def add_handler(self, handler: Callable[[_Sender], None]) -> None:
        """
        Add another handler to this callback.
        """
        self._handlers.append(handler)

    def remove_handler(self, handler: Callable[[_Sender], None]) -> None:
        """
        Remove a handler from this callback.
        """
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass

    def __iadd__(self, handler: Callable[[_Sender], None]) -> Event[_Sender]:
        self.add_handler(handler)
        return self

    def __isub__(self, handler: Callable[[_Sender], None]) -> Event[_Sender]:
        self.remove_handler(handler)
        return self


class DummyContext(AbstractContextManager[None]):
    """
    (contextlib.nested is not available on Py3)
    """

    def __enter__(self) -> None:
        pass

    def __exit__(self, *a: object) -> None:
        pass


class _CharSizesCache(dict[str, int]):
    """
    Cache for wcwidth sizes.
    """

    LONG_STRING_MIN_LEN = 64
    MAX_LONG_STRINGS = 16

    def __init__(self) -> None:
        super().__init__()
        self._long_strings: deque[str] = deque()

    def __missing__(self, string: str) -> int:
        # Note: We use max(0, ...) because some non-printable control
        # characters return -1 from wcwidth.
        if len(string) == 1:
            result = max(0, wcwidth(string))
        else:
            result = sum(map(self.__getitem__, string))

        self[string] = result

        if len(string) > self.LONG_STRING_MIN_LEN:
            long_strings = self._long_strings
            long_strings.append(string)

            if len(long_strings) > self.MAX_LONG_STRINGS:
                self.pop(long_strings.popleft(), None)

        return result


_CHAR_SIZES_CACHE = _CharSizesCache()


def get_cwidth(string: str) -> int:
    """
    Return width of a string. Wrapper around ``wcwidth``.
    """
    return _CHAR_SIZES_CACHE[string]


def suspend_to_background_supported() -> bool:
    """
    Returns `True` when the Python implementation supports
    suspend-to-background.
    """
    return hasattr(signal, "SIGTSTP")


def is_windows() -> bool:
    """
    True when we are using Windows.
    """
    return sys.platform == "win32"


def is_windows_vt100_supported() -> bool:
    """
    True when we are using Windows, but VT100 escape sequences are supported.
    """
    if sys.platform != "win32":
        return False

    from prompt_toolkit.output.windows10 import is_win_vt100_enabled

    return is_win_vt100_enabled()


def is_conemu_ansi() -> bool:
    """
    True when the ConEmu Windows console is used.
    """
    return (
        sys.platform == "win32"
        and os.environ.get("ConEmuANSI", "OFF") == "ON"
    )


def in_main_thread() -> bool:
    """
    True when the current thread is the main thread.
    """
    return threading.current_thread() is threading.main_thread()


def get_bell_environment_variable() -> bool:
    """
    True if env variable is set to true (true, TRUE, True, 1).
    """
    return os.environ.get("PROMPT_TOOLKIT_BELL", "true").lower() in {
        "1",
        "true",
    }


def get_term_environment_variable() -> str:
    """Return the $TERM environment variable."""
    return os.environ.get("TERM", "")


def take_using_weights(
    items: list[_T],
    weights: list[int],
) -> Generator[_T, None, None]:
    """
    Generator that keeps yielding items from the items list,
    in proportion to their weight.
    """
    assert len(items) == len(weights)
    assert items

    filtered = [(item, w) for item, w in zip(items, weights) if w > 0]

    if not filtered:
        raise ValueError("Didn't get any items with a positive weight.")

    items, weights = map(list, zip(*filtered))

    already_taken = [0] * len(items)
    max_weight = max(weights)

    i = 0
    while True:
        adding = True

        while adding:
            adding = False

            for item_i, (item, weight) in enumerate(zip(items, weights)):
                if already_taken[item_i] < i * weight / max_weight:
                    yield item
                    already_taken[item_i] += 1
                    adding = True

        i += 1


def to_str(value: Callable[[], str] | str) -> str:
    """Turn callable or string into string."""
    while callable(value):
        value = value()

    return str(value)


def to_int(value: Callable[[], int] | int) -> int:
    """Turn callable or int into int."""
    while callable(value):
        value = value()

    return int(value)


AnyFloat = Callable[[], float] | float


def to_float(value: AnyFloat) -> float:
    """Turn callable or float into float."""
    while callable(value):
        value = value()

    return float(value)


def is_dumb_terminal(term: str | None = None) -> bool:
    """
    True if this terminal type is considered "dumb".
    """
    if term is None:
        term = os.environ.get("TERM", "")

    return term.lower() in {"dumb", "unknown"}
