#!/usr/bin/env python
"""
Read input and print pressed keys.
Useful for testing terminal input.

Works on both Windows and POSIX systems.
"""

from __future__ import annotations

import asyncio

from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys


async def main() -> None:
    """
    Create an input handler and continuously print pressed keys
    until Ctrl+C is received.
    """
    done = asyncio.Event()
    input = create_input()

    def keys_ready() -> None:
        """
        Callback executed when input is available.
        """
        for key_press in input.read_keys():
            print(key_press)

            if key_press.key is Keys.ControlC:
                done.set()
                return

    with input.raw_mode(), input.attach(keys_ready):
        await done.wait()


if __name__ == "__main__":
    asyncio.run(main())
