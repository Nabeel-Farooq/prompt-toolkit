"""
Async Telnet server implementation.
"""

from __future__ import annotations

import asyncio
import contextvars
import socket
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import Callable, Coroutine
from typing import Any, Final, TextIO, cast

from prompt_toolkit.application.current import create_app_session, get_app
from prompt_toolkit.application.run_in_terminal import run_in_terminal
from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import AnyFormattedText, to_formatted_text
from prompt_toolkit.input import PipeInput, create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.renderer import print_formatted_text
from prompt_toolkit.styles import BaseStyle, DummyStyle

from .log import logger
from .protocol import (
    DO,
    ECHO,
    IAC,
    LINEMODE,
    MODE,
    NAWS,
    SB,
    SE,
    SEND,
    SUPPRESS_GO_AHEAD,
    TTYPE,
    WILL,
    TelnetProtocolParser,
)

__all__ = ["TelnetServer"]


def _byte(value: int) -> bytes:
    return bytes((value,))


_SOCKET_BUFFER_SIZE: Final = 4096
_DEFAULT_SIZE: Final = Size(rows=40, columns=79)


# ============================================================================
# Telnet initialization
# ============================================================================


def _send_negotiation(connection: socket.socket, *parts: bytes) -> None:
    """Send a Telnet negotiation sequence."""
    connection.sendall(b"".join(parts))


def _initialize_telnet(connection: socket.socket) -> None:
    """
    Initialize Telnet option negotiation.
    """
    logger.info("Initializing telnet connection")

    negotiations = (
        (IAC, DO, LINEMODE),
        (IAC, WILL, SUPPRESS_GO_AHEAD),
        (IAC, SB, LINEMODE, MODE, _byte(0), IAC, SE),
        (IAC, WILL, ECHO),
        (IAC, DO, NAWS),
        (IAC, DO, TTYPE),
        (IAC, SB, TTYPE, SEND, IAC, SE),
    )

    for sequence in negotiations:
        _send_negotiation(connection, *sequence)


# ============================================================================
# Socket-backed stdout
# ============================================================================


class _ConnectionStdout:
    """
    File-like stdout wrapper around a socket.
    """

    def __init__(self, connection: socket.socket, encoding: str) -> None:
        self._connection = connection
        self._encoding = encoding
        self._errors = "strict"
        self._closed = False
        self._buffer = bytearray()

    @property
    def encoding(self) -> str:
        return self._encoding

    @property
    def errors(self) -> str:
        return self._errors

    def isatty(self) -> bool:
        return True

    def write(self, data: str) -> None:
        if self._closed:
            return

        normalized = data.replace("\n", "\r\n")
        self._buffer.extend(
            normalized.encode(self._encoding, errors=self._errors)
        )

        self.flush()

    def flush(self) -> None:
        if self._closed or not self._buffer:
            return

        try:
            self._connection.sendall(self._buffer)
        except OSError as exc:
            logger.warning("Failed to send socket data: %s", exc)
        finally:
            self._buffer.clear()

    def close(self) -> None:
        self._closed = True
        self._buffer.clear()


# ============================================================================
# Connection
# ============================================================================


class TelnetConnection:
    """
    Represents a single Telnet client connection.
    """

    def __init__(
        self,
        conn: socket.socket,
        addr: tuple[str, int],
        interact: Callable[[TelnetConnection], Coroutine[Any, Any, None]],
        server: TelnetServer,
        encoding: str,
        style: BaseStyle | None,
        vt100_input: PipeInput,
        enable_cpr: bool = True,
    ) -> None:
        self.conn = conn
        self.addr = addr
        self.interact = interact
        self.server = server

        self.encoding = encoding
        self.style = style
        self.enable_cpr = enable_cpr

        self.vt100_input = vt100_input
        self.vt100_output: Vt100_Output | None = None

        self.size = _DEFAULT_SIZE

        self._closed = False
        self._ready = asyncio.Event()

        self.context: contextvars.Context | None = None

        self.stdout = cast(
            TextIO,
            _ConnectionStdout(conn, encoding=encoding),
        )

        _initialize_telnet(conn)

        self.parser = TelnetProtocolParser(
            self._on_data_received,
            self._on_size_received,
            self._on_terminal_type_received,
        )

    # ------------------------------------------------------------------
    # Parser callbacks
    # ------------------------------------------------------------------

    def _on_data_received(self, data: bytes) -> None:
        self.vt100_input.send_bytes(data)

    def _on_size_received(self, rows: int, columns: int) -> None:
        self.size = Size(rows=rows, columns=columns)

        if self.vt100_output and self.context:
            self.context.run(lambda: get_app()._on_resize())

    def _on_terminal_type_received(self, terminal_type: str) -> None:
        self.vt100_output = Vt100_Output(
            stdout=self.stdout,
            get_size=lambda: self.size,
            term=terminal_type,
            enable_cpr=self.enable_cpr,
        )

        self._ready.set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run_application(self) -> None:
        """
        Run the interactive Telnet application.
        """
        loop = get_running_loop()

        def handle_incoming_data() -> None:
            try:
                data = self.conn.recv(_SOCKET_BUFFER_SIZE)
            except OSError as exc:
                logger.warning("Socket receive failed: %s", exc)
                self.close()
                return

            if not data:
                logger.info(
                    "Connection closed by client %s:%s",
                    *self.addr,
                )
                self.close()
                return

            self.feed(data)

        loop.add_reader(self.conn, handle_incoming_data)

        try:
            await self._ready.wait()

            with create_app_session(
                input=self.vt100_input,
                output=self.vt100_output,
            ):
                self.context = contextvars.copy_context()
                await self.interact(self)

        finally:
            self.close()

    def feed(self, data: bytes) -> None:
        """Feed incoming bytes into the Telnet parser."""
        self.parser.feed(data)

    def close(self) -> None:
        """
        Close the Telnet connection.
        """
        if self._closed:
            return

        self._closed = True

        loop = get_running_loop()

        try:
            loop.remove_reader(self.conn)
        except Exception:
            pass

        try:
            self.vt100_input.close()
        except Exception:
            pass

        try:
            self.conn.close()
        except Exception:
            pass

        self.stdout.close()

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def send(self, formatted_text: AnyFormattedText) -> None:
        """
        Send formatted text to the client.
        """
        if self.vt100_output is None:
            return

        print_formatted_text(
            output=self.vt100_output,
            formatted_text=to_formatted_text(formatted_text),
            style=self.style or DummyStyle(),
        )

    def send_above_prompt(self, formatted_text: AnyFormattedText) -> None:
        """
        Print text above the active prompt/application.
        """
        self._run_in_terminal(
            lambda: self.send(to_formatted_text(formatted_text))
        )

    def _run_in_terminal(self, func: Callable[[], None]) -> None:
        if self.context is None:
            raise RuntimeError(
                "_run_in_terminal called outside run_application()"
            )

        self.context.run(run_in_terminal, func)

    def erase_screen(self) -> None:
        """
        Clear the terminal screen.
        """
        if self.vt100_output is None:
            return

        self.vt100_output.erase_screen()
        self.vt100_output.cursor_goto(0, 0)
        self.vt100_output.flush()


# ============================================================================
# Default interaction
# ============================================================================


async def _dummy_interact(connection: TelnetConnection) -> None:
    """Fallback interaction handler."""
    return None


# ============================================================================
# Server
# ============================================================================


class TelnetServer:
    """
    Async Telnet server.

    Example:
        ```python
        async def interact(connection):
            connection.send("Welcome\\n")

        server = TelnetServer(port=2323, interact=interact)
        await server.run()
        ```
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 23,
        interact: Callable[
            [TelnetConnection],
            Coroutine[Any, Any, None],
        ] = _dummy_interact,
        encoding: str = "utf-8",
        style: BaseStyle | None = None,
        enable_cpr: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.interact = interact

        self.encoding = encoding
        self.style = style
        self.enable_cpr = enable_cpr

        self.connections: set[TelnetConnection] = set()

        self._run_task: asyncio.Task[None] | None = None
        self._application_tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------
    # Socket management
    # ------------------------------------------------------------------

    @staticmethod
    def _create_socket(host: str, port: int) -> socket.socket:
        """
        Create listening socket.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        sock.bind((host, port))
        sock.listen()
        sock.setblocking(False)

        return sock

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def run(
        self,
        ready_cb: Callable[[], None] | None = None,
    ) -> None:
        """
        Run the Telnet server until cancelled.
        """
        listen_socket = self._create_socket(self.host, self.port)

        logger.info(
            "Listening for Telnet connections on %s:%s",
            self.host,
            self.port,
        )

        loop = get_running_loop()
        loop.add_reader(
            listen_socket,
            lambda: self._accept(listen_socket),
        )

        if ready_cb:
            ready_cb()

        try:
            await asyncio.Future()

        finally:
            loop.remove_reader(listen_socket)
            listen_socket.close()

            for task in self._application_tasks:
                task.cancel()

            if self._application_tasks:
                await asyncio.gather(
                    *self._application_tasks,
                    return_exceptions=True,
                )

    def start(self) -> None:
        """
        Deprecated compatibility API.
        """
        if self._run_task is not None:
            return

        self._run_task = get_running_loop().create_task(self.run())

    async def stop(self) -> None:
        """
        Deprecated compatibility API.
        """
        if self._run_task is None:
            return

        self._run_task.cancel()

        try:
            await self._run_task
        except asyncio.CancelledError:
            pass

        self._run_task = None

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    def _accept(self, listen_socket: socket.socket) -> None:
        """
        Accept incoming Telnet connection.
        """
        try:
            conn, addr = listen_socket.accept()
        except OSError as exc:
            logger.warning("Accept failed: %s", exc)
            return

        logger.info("New connection %s:%s", *addr)

        task = get_running_loop().create_task(
            self._handle_connection(conn, addr)
        )

        self._application_tasks.add(task)
        task.add_done_callback(self._application_tasks.discard)

    async def _handle_connection(
        self,
        conn: socket.socket,
        addr: tuple[str, int],
    ) -> None:
        """
        Handle a single client connection.
        """
        try:
            with create_pipe_input() as vt100_input:
                connection = TelnetConnection(
                    conn=conn,
                    addr=addr,
                    interact=self.interact,
                    server=self,
                    encoding=self.encoding,
                    style=self.style,
                    vt100_input=vt100_input,
                    enable_cpr=self.enable_cpr,
                )

                self.connections.add(connection)

                logger.info(
                    "Starting interaction %s:%s",
                    *addr,
                )

                try:
                    await connection.run_application()

                finally:
                    self.connections.discard(connection)

                    logger.info(
                        "Stopping interaction %s:%s",
                        *addr,
                    )

        except EOFError:
            logger.info("Unhandled EOFError in telnet session")

        except KeyboardInterrupt:
            logger.info("Unhandled KeyboardInterrupt in telnet session")

        except Exception:
            logger.exception(
                "Unhandled exception in telnet session %s:%s",
                *addr,
            )
