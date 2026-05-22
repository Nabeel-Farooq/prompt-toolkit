"""
Minimal Telnet protocol parser.

This implementation is intentionally lightweight and focused on
interactive terminal sessions rather than full RFC compliance.

Inspired by Twisted's `conch.telnet`.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Generator
from typing import Final

from .log import logger

__all__ = ["TelnetProtocolParser"]


def _byte(value: int) -> bytes:
    """Convert an integer into a single-byte bytes object."""
    return bytes((value,))


# Telnet command constants.
IAC: Final = _byte(255)  # Interpret As Command
DONT: Final = _byte(254)
DO: Final = _byte(253)
WONT: Final = _byte(252)
WILL: Final = _byte(251)
SB: Final = _byte(250)  # Subnegotiation Begin
GA: Final = _byte(249)
EL: Final = _byte(248)
EC: Final = _byte(247)
AYT: Final = _byte(246)
AO: Final = _byte(245)
IP: Final = _byte(244)
BRK: Final = _byte(243)
DM: Final = _byte(242)
SE: Final = _byte(240)  # Subnegotiation End

# Telnet options.
ECHO: Final = _byte(1)
SGA: Final = _byte(3)  # Suppress Go Ahead
NAWS: Final = _byte(31)  # Negotiate About Window Size
TTYPE: Final = _byte(24)  # Terminal Type
LINEMODE: Final = _byte(34)

# Subnegotiation values.
IS: Final = _byte(0)
SEND: Final = _byte(1)
MODE: Final = _byte(1)

# Simple commands handled without payload.
_SIMPLE_COMMANDS: Final = {
    NOP := _byte(0),
    DM,
    BRK,
    IP,
    AO,
    AYT,
    EC,
    EL,
    GA,
}

# Negotiation commands.
_NEGOTIATION_COMMANDS: Final = {DO, DONT, WILL, WONT}


class TelnetProtocolParser:
    """
    Incremental Telnet protocol parser.

    Example:
        ```python
        parser = TelnetProtocolParser(
            data_received_callback=print,
            size_received_callback=lambda r, c: print(r, c),
            ttype_received_callback=print,
        )

        parser.feed(binary_data)
        ```
    """

    def __init__(
        self,
        data_received_callback: Callable[[bytes], None],
        size_received_callback: Callable[[int, int], None],
        ttype_received_callback: Callable[[str], None],
    ) -> None:
        self.data_received_callback = data_received_callback
        self.size_received_callback = size_received_callback
        self.ttype_received_callback = ttype_received_callback

        self._parser = self._parse_coroutine()
        next(self._parser)

    # ------------------------------------------------------------------
    # Public callbacks
    # ------------------------------------------------------------------

    def received_data(self, data: bytes) -> None:
        """Handle regular incoming data."""
        self.data_received_callback(data)

    def do_received(self, option: bytes) -> None:
        logger.info("DO %r", option)

    def dont_received(self, option: bytes) -> None:
        logger.info("DONT %r", option)

    def will_received(self, option: bytes) -> None:
        logger.info("WILL %r", option)

    def wont_received(self, option: bytes) -> None:
        logger.info("WONT %r", option)

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def command_received(self, command: bytes, option: bytes) -> None:
        """Dispatch negotiation commands."""
        handlers = {
            DO: self.do_received,
            DONT: self.dont_received,
            WILL: self.will_received,
            WONT: self.wont_received,
        }

        handler = handlers.get(command)

        if handler is not None:
            handler(option)
        else:
            logger.info("Unhandled command: %r %r", command, option)

    # ------------------------------------------------------------------
    # Subnegotiation handling
    # ------------------------------------------------------------------

    def naws(self, payload: bytes) -> None:
        """
        Handle NAWS (Negotiate About Window Size).

        Payload format:
            - 2 bytes: columns
            - 2 bytes: rows
        """
        if len(payload) != 4:
            logger.warning("Invalid NAWS payload length: %d", len(payload))
            return

        columns, rows = struct.unpack("!HH", payload)
        self.size_received_callback(rows, columns)

    def ttype(self, payload: bytes) -> None:
        """
        Handle terminal type negotiation.
        """
        if not payload:
            logger.warning("Empty TTYPE payload")
            return

        subcommand = payload[:1]
        terminal_data = payload[1:]

        if subcommand != IS:
            logger.warning("Unsupported TTYPE subcommand: %r", subcommand)
            return

        try:
            terminal_type = terminal_data.decode("ascii")
        except UnicodeDecodeError:
            logger.warning("Invalid terminal type encoding")
            return

        self.ttype_received_callback(terminal_type)

    def negotiate(self, payload: bytes) -> None:
        """
        Handle subnegotiation payloads.
        """
        if not payload:
            logger.warning("Empty negotiation payload")
            return

        option = payload[:1]
        option_payload = payload[1:]

        if option == NAWS:
            self.naws(option_payload)

        elif option == TTYPE:
            self.ttype(option_payload)

        else:
            logger.debug(
                "Unhandled negotiation option %r (%d bytes)",
                option,
                len(option_payload),
            )

    # ------------------------------------------------------------------
    # Parser state machine
    # ------------------------------------------------------------------

    def _parse_coroutine(self) -> Generator[None, bytes, None]:
        """
        Incremental Telnet parser state machine.

        Each `yield` receives exactly one byte.
        """
        while True:
            byte = yield

            # Ignore NULL bytes.
            if byte == b"\x00":
                continue

            # Regular data byte.
            if byte != IAC:
                self.received_data(byte)
                continue

            # Escaped Telnet command sequence.
            command = yield

            # Escaped IAC byte.
            if command == IAC:
                self.received_data(IAC)
                continue

            # Simple one-byte commands.
            if command in _SIMPLE_COMMANDS:
                self.command_received(command, b"")
                continue

            # Negotiation commands with single-byte payload.
            if command in _NEGOTIATION_COMMANDS:
                option = yield
                self.command_received(command, option)
                continue

            # Subnegotiation sequence.
            if command == SB:
                buffer = bytearray()

                while True:
                    chunk = yield

                    if chunk != IAC:
                        buffer.extend(chunk)
                        continue

                    escaped = yield

                    # End of subnegotiation.
                    if escaped == SE:
                        break

                    # Escaped byte inside payload.
                    buffer.extend(escaped)

                self.negotiate(bytes(buffer))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self, data: bytes) -> None:
        """
        Feed raw Telnet data into the parser.
        """
        parser = self._parser.send

        for value in data:
            parser(_byte(value))
