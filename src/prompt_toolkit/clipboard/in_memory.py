from __future__ import annotations

from collections import deque

from .base import Clipboard, ClipboardData

__all__ = [
    "InMemoryClipboard",
]


class InMemoryClipboard(Clipboard):
    """
    Default in-memory clipboard implementation.

    Stores clipboard history in a kill ring, primarily used for Emacs mode.
    """

    def __init__(
        self,
        data: ClipboardData | None = None,
        max_size: int = 60,
    ) -> None:
        if max_size < 1:
            raise ValueError("max_size must be at least 1.")

        self.max_size = max_size

        # Using `maxlen` automatically trims old entries.
        self._ring: deque[ClipboardData] = deque(maxlen=max_size)

        if data is not None:
            self.set_data(data)

    def set_data(self, data: ClipboardData) -> None:
        """
        Add clipboard data to the front of the kill ring.
        """
        self._ring.appendleft(data)

    def get_data(self) -> ClipboardData:
        """
        Return the most recent clipboard entry.
        """
        if self._ring:
            return self._ring[0]

        return ClipboardData()

    def rotate(self) -> None:
        """
        Rotate the kill ring.

        The current item moves to the end, exposing the next entry.
        """
        if self._ring:
            self._ring.append(self._ring.popleft())
