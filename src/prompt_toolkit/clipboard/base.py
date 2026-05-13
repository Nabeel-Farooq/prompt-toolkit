"""
Clipboard abstractions for command line interfaces.
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Callable

from prompt_toolkit.selection import SelectionType

__all__ = [
    "Clipboard",
    "ClipboardData",
    "DummyClipboard",
    "DynamicClipboard",
]


class ClipboardData:
    """
    Data stored on the clipboard.

    :param text:
        Clipboard text content.
    :param type:
        :class:`~prompt_toolkit.selection.SelectionType`
    """

    __slots__ = ("text", "type")

    def __init__(
        self,
        text: str = "",
        type: SelectionType = SelectionType.CHARACTERS,
    ) -> None:
        self.text = text
        self.type = type

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"text={self.text!r}, type={self.type!r})"
        )


class Clipboard(metaclass=ABCMeta):
    """
    Abstract base class for clipboard implementations.

    Clipboard implementations may:
    - store data in memory
    - integrate with system clipboards (X11/Windows/macOS)
    - persist clipboard history
    """

    @abstractmethod
    def set_data(self, data: ClipboardData) -> None:
        """
        Store clipboard data.

        :param data:
            :class:`~.ClipboardData` instance.
        """

    def set_text(self, text: str) -> None:
        """
        Convenience method for storing plain text.
        """
        self.set_data(ClipboardData(text=text))

    def rotate(self) -> None:
        """
        Rotate clipboard history / kill ring.

        Primarily used by Emacs mode.
        """

    @abstractmethod
    def get_data(self) -> ClipboardData:
        """
        Retrieve clipboard data.
        """


class DummyClipboard(Clipboard):
    """
    Clipboard implementation that stores nothing.
    """

    _EMPTY_DATA = ClipboardData()

    def set_data(self, data: ClipboardData) -> None:
        return None

    def set_text(self, text: str) -> None:
        return None

    def rotate(self) -> None:
        return None

    def get_data(self) -> ClipboardData:
        return self._EMPTY_DATA


class DynamicClipboard(Clipboard):
    """
    Clipboard wrapper that dynamically resolves another clipboard instance.

    :param get_clipboard:
        Callable returning a :class:`.Clipboard` instance or `None`.
    """

    def __init__(
        self,
        get_clipboard: Callable[[], Clipboard | None],
    ) -> None:
        self.get_clipboard = get_clipboard

    def _clipboard(self) -> Clipboard:
        """
        Return the active clipboard implementation.
        """
        return self.get_clipboard() or DummyClipboard()

    def set_data(self, data: ClipboardData) -> None:
        self._clipboard().set_data(data)

    def set_text(self, text: str) -> None:
        self._clipboard().set_text(text)

    def rotate(self) -> None:
        self._clipboard().rotate()

    def get_data(self) -> ClipboardData:
        return self._clipboard().get_data()
