#!/usr/bin/env python
"""
Parse VT100 input and print pressed keys.
Useful for testing terminal input behavior.

(This intentionally uses `Vt100Parser` directly instead of the `Input` API.)
"""

from __future__ import annotations

import sys

from prompt_toolkit.input.vt100 import raw_mode
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys


def callback(key_press: KeyPress) -> None:
    """
    Handle parsed key presses.
    """
    print(key_press)

    if key_press.key is Keys.ControlC:
        raise SystemExit(0)


def main() -> None:
    """
    Read terminal input in raw mode and feed it into the VT100 parser.
    """
    stdin = sys.stdin
    fileno = stdin.fileno()

    stream = Vt100Parser(callback)

    with raw_mode(fileno):
        while True:
            char = stdin.read(1)

            # EOF / stream closed safeguard.
            if not char:
                break

            stream.feed(char)


if __name__ == "__main__":
    main()
