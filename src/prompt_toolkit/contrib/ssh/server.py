"""
Utilities for running prompt_toolkit applications over AsyncSSH.
"""

from __future__ import annotations

import asyncio
from asyncio import get_running_loop
from collections.abc import Callable, Coroutine
from typing import Any, Final, TextIO, cast

import asyncssh

from prompt_toolkit.application.current import AppSession, create_app_session
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import PipeInput, create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output

from .log import logger

__all__ = [
    "PromptToolkitSSHSession",
    "PromptToolkitSSHServer",
]


_DEFAULT_SIZE: Final = Size(rows=24, columns=80)


# ============================================================================
# Stdout wrapper
# ============================================================================


class _SSHStdout:
    """
    File-like stdout wrapper for AsyncSSH channels.
    """

    def __init__(self, session: PromptToolkitSSHSession) -> None:
        self._session = session

    @property
    def _channel(self) -> Any:
        return self._session.channel

    def write(self, data: str) -> None:
        channel = self._channel

        if channel is None:
            return

        try:
            channel.write(data.replace("\n", "\r\n"))
        except BrokenPipeError:
            logger.debug("SSH channel closed while writing output")

    def flush(self) -> None:
        """Compatibility no-op."""

    def isatty(self) -> bool:
        return True

    @property
    def encoding(self) -> str:
        channel = self._channel

        if channel is None:
            return "utf-8"

        try:
            return str(channel._orig_chan.get_encoding()[0])
        except Exception:
            return "utf-8"


# ============================================================================
# SSH session
# ============================================================================


class PromptToolkitSSHSession(asyncssh.SSHServerSession):  # type: ignore[misc]
    """
    AsyncSSH session running a prompt_toolkit application.
    """

    def __init__(
        self,
        interact: Callable[
            [PromptToolkitSSHSession],
            Coroutine[Any, Any, None],
        ],
        *,
        enable_cpr: bool,
    ) -> None:
        self.interact = interact
        self.enable_cpr = enable_cpr

        self.interact_task: asyncio.Task[None] | None = None

        self.channel: Any | None = None

        self.app_session: AppSession | None = None

        self._input: PipeInput | None = None
        self._output: Vt100_Output | None = None

        self.stdout = cast(TextIO, _SSHStdout(self))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_size(self) -> Size:
        """
        Return current terminal dimensions.
        """
        if self.channel is None:
            return _DEFAULT_SIZE

        try:
            width, height, _, _ = self.channel.get_terminal_size()
            return Size(rows=height, columns=width)

        except Exception:
            return _DEFAULT_SIZE

    def _create_output(self) -> Vt100_Output:
        """
        Create prompt_toolkit VT100 output instance.
        """
        assert self.channel is not None

        return Vt100_Output(
            stdout=self.stdout,
            get_size=self._get_size,
            term=self.channel.get_terminal_type(),
            enable_cpr=self.enable_cpr,
        )

    # ------------------------------------------------------------------
    # AsyncSSH callbacks
    # ------------------------------------------------------------------

    def connection_made(self, chan: Any) -> None:
        self.channel = chan

    def shell_requested(self) -> bool:
        return True

    def session_started(self) -> None:
        self.interact_task = get_running_loop().create_task(
            self._interact()
        )

    async def _interact(self) -> None:
        """
        Start interactive prompt_toolkit session.
        """
        if self.channel is None:
            raise RuntimeError(
                "_interact() called before connection_made()"
            )

        self._disable_asyncssh_line_mode()

        self._output = self._create_output()

        try:
            with create_pipe_input() as pipe_input:
                self._input = pipe_input

                with create_app_session(
                    input=pipe_input,
                    output=self._output,
                ) as session:
                    self.app_session = session

                    await self.interact(self)

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Unhandled exception in SSH session")

        finally:
            self.close()

    def terminal_size_changed(
        self,
        width: int,
        height: int,
        pixwidth: object,
        pixheight: object,
    ) -> None:
        """
        Notify prompt_toolkit application about terminal resize.
        """
        if self.app_session and self.app_session.app:
            self.app_session.app._on_resize()

    def data_received(self, data: str, datatype: object) -> None:
        """
        Forward incoming SSH data to prompt_toolkit input.
        """
        if self._input is None:
            return

        self._input.send_text(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _disable_asyncssh_line_mode(self) -> None:
        """
        Disable AsyncSSH line editing.

        prompt_toolkit handles line editing itself.
        """
        channel = self.channel

        if channel is None:
            return

        try:
            if (
                hasattr(channel, "set_line_mode")
                and channel._editor is not None
            ):
                channel.set_line_mode(False)

        except Exception:
            logger.debug("Failed to disable AsyncSSH line mode")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """
        Close SSH session resources.
        """
        try:
            if self._input is not None:
                self._input.close()
        except Exception:
            pass

        try:
            if self.channel is not None:
                self.channel.close()
        except Exception:
            pass


# ============================================================================
# SSH server
# ============================================================================


class PromptToolkitSSHServer(asyncssh.SSHServer):
    """
    AsyncSSH server wrapper for prompt_toolkit applications.

    Example:
        ```python
        async def interact(session):
            ...

        await asyncssh.create_server(
            lambda: PromptToolkitSSHServer(interact),
            "",
            8022,
            server_host_keys=["ssh_host_key"],
        )
        ```
    """

    def __init__(
        self,
        interact: Callable[
            [PromptToolkitSSHSession],
            Coroutine[Any, Any, None],
        ],
        *,
        enable_cpr: bool = True,
    ) -> None:
        self.interact = interact
        self.enable_cpr = enable_cpr

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def begin_auth(self, username: str) -> bool:
        """
        Disable authentication.

        Override this in subclasses for real authentication.
        """
        return False

    # ------------------------------------------------------------------
    # Session creation
    # ------------------------------------------------------------------

    def session_requested(self) -> PromptToolkitSSHSession:
        """
        Create SSH session instance.
        """
        return PromptToolkitSSHSession(
            self.interact,
            enable_cpr=self.enable_cpr,
        )
