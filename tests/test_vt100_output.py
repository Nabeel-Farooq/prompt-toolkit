from __future__ import annotations

import pytest

from prompt_toolkit.output.vt100 import (
    _256_colors,
    _get_closest_ansi_color,
)


@pytest.mark.parametrize(
    ("rgb", "expected"),
    [
        # White
        ((255, 255, 255), "ansiwhite"),
        ((250, 250, 250), "ansiwhite"),

        # Black
        ((0, 0, 0), "ansiblack"),
        ((5, 5, 5), "ansiblack"),

        # Green
        ((0, 255, 0), "ansibrightgreen"),
        ((10, 255, 0), "ansibrightgreen"),
        ((0, 255, 10), "ansibrightgreen"),

        # Yellow
        ((220, 220, 100), "ansiyellow"),
    ],
)
def test_get_closest_ansi_color(
    rgb: tuple[int, int, int],
    expected: str,
) -> None:
    assert _get_closest_ansi_color(*rgb) == expected


@pytest.mark.parametrize(
    ("rgb", "expected"),
    [
        # 6×6×6 color cube
        ((0, 0, 0), 16),
        ((255, 255, 255), 231),
        ((95, 95, 95), 59),

        # Grayscale
        ((8, 8, 8), 232),
        ((238, 238, 238), 255),
    ],
)
def test_256_color_lookup(
    rgb: tuple[int, int, int],
    expected: int,
) -> None:
    assert _256_colors[rgb] == expected
