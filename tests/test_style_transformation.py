from __future__ import annotations

import pytest

from prompt_toolkit.styles import (
    AdjustBrightnessStyleTransformation,
    Attrs,
)


@pytest.fixture
def default_attrs() -> Attrs:
    return Attrs(
        color="",
        bgcolor="",
        bold=False,
        underline=False,
        strike=False,
        italic=False,
        blink=False,
        reverse=False,
        hidden=False,
        dim=False,
    )


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("ff0000", "ff7f7f"),
        ("00ffaa", "7fffd4"),
        ("ansiblue", "6666ff"),
        ("ansidefault", "ansidefault"),
    ],
)
def test_adjust_brightness_transformation(
    default_attrs: Attrs,
    color: str,
    expected: str,
) -> None:
    transformer = AdjustBrightnessStyleTransformation(
        min_brightness=0.5,
        max_brightness=1.0,
    )

    attrs = transformer.transform_attrs(
        default_attrs._replace(color=color)
    )

    assert attrs.color == expected


def test_background_color_prevents_transformation(
    default_attrs: Attrs,
) -> None:
    transformer = AdjustBrightnessStyleTransformation(
        min_brightness=0.5,
        max_brightness=1.0,
    )

    attrs = transformer.transform_attrs(
        default_attrs._replace(
            color="00ffaa",
            bgcolor="white",
        )
    )

    assert attrs.color == "00ffaa"


@pytest.mark.parametrize(
    "color",
    [
        "ansiblue",
        "00ffaa",
    ],
)
def test_identity_transformation(
    default_attrs: Attrs,
    color: str,
) -> None:
    transformer = AdjustBrightnessStyleTransformation(
        min_brightness=0,
        max_brightness=1,
    )

    attrs = transformer.transform_attrs(
        default_attrs._replace(color=color)
    )

    assert attrs.color == color
