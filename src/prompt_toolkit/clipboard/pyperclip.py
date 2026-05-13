from __future__ import annotations

import pyperclip

from prompt_toolkit.selection import SelectionType

from .base import Clipboard, ClipboardData

__all__ = [
    "PyperclipClipboard",
]


class PyperclipClipboard(Clipboard):
    """
    Clipboard implementation that synchronizes with the system clipboard
    using the `pyperclip` module.

    Supports Windows, macOS, and Linux.
    """

    def __init__(self) -> None:
        # Cache the most recently copied ClipboardData instance so we can
        # preserve SelectionType metadata when possible.
        self._data: ClipboardData | None = None

    def set_data(self, data: ClipboardData) -> None:
        """
        Store clipboard data locally and sync it to the system clipboard.
        """
        self._data = data
        pyperclip.copy(data.text)

    def get_data(self) -> ClipboardData:
        """
        Retrieve clipboard data from the system clipboard.
        """
        text = pyperclip.paste()

        # Reuse cached ClipboardData to preserve SelectionType metadata.
        if self._data is not None and self._data.text == text:
            return self._data

        # Infer selection type from clipboard content.
        selection_type = (
            SelectionType.LINES
            if "\n" in text
            else SelectionType.CHARACTERS
        )

        return ClipboardData(
            text=text,
            type=selection_type,
        )
