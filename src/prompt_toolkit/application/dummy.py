from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.eventloop import InputHook
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

from .application import Application

__all__ = ["DummyApplication"]


class DummyApplication(Application[None]):
    """
    Fallback application used when no real :class:`.Application`
    instance is currently running.

    :func:`.get_app` returns this dummy implementation to provide a
    safe placeholder object.
    """

    _ERROR_MESSAGE = "A DummyApplication is not supposed to run."

    def __init__(self) -> None:
        super().__init__(
            output=DummyOutput(),
            input=DummyInput(),
        )

    @staticmethod
    def _raise_not_supported() -> None:
        """
        Raise a consistent error for unsupported operations.
        """
        raise NotImplementedError(DummyApplication._ERROR_MESSAGE)

    def run(
        self,
        pre_run: Callable[[], None] | None = None,
        set_exception_handler: bool = True,
        handle_sigint: bool = True,
        in_thread: bool = False,
        inputhook: InputHook | None = None,
    ) -> None:
        self._raise_not_supported()

    async def run_async(
        self,
        pre_run: Callable[[], None] | None = None,
        set_exception_handler: bool = True,
        handle_sigint: bool = True,
        slow_callback_duration: float = 0.5,
    ) -> None:
        self._raise_not_supported()

    async def run_system_command(
        self,
        command: str,
        wait_for_enter: bool = True,
        display_before_text: AnyFormattedText = "",
        wait_text: str = "",
    ) -> None:
        self._raise_not_supported()

    def suspend_to_background(self, suspend_group: bool = True) -> None:
        self._raise_not_supported()
