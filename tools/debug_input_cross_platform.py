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
    done = asyncio.get_running_loop().create_future()
    input_stream = create_input()

    def keys_ready() -> None:
        """
        Callback executed when input is available.
        """
        for key_press in input_stream.read_keys():
            print(key_press)

            if key_press.key is Keys.ControlC and not done.done():
                done.set_result(None)
                return

    with input_stream.raw_mode(), input_stream.attach(keys_ready):
        await done


if __name__ == "__main__":
    asyncio.run(main())
