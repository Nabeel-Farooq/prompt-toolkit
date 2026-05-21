from __future__ import annotations

import pytest

from prompt_toolkit.styles import Attrs, Style, SwapLightAndDarkStyleTransformation


def attrs(**kwargs) -> Attrs:
    """Helper to reduce boilerplate in Attrs creation."""
    defaults = dict(
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
    defaults.update(kwargs)
    return Attrs(**defaults)


def test_style_from_dict():
    style = Style.from_dict(
        {
            "a": "#ff0000 bold underline strike italic",
            "b": "bg:#00ff00 blink reverse",
        }
    )

    assert style.get_attrs_for_style_str("class:a") == attrs(
        color="ff0000",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
    )

    assert style.get_attrs_for_style_str("class:b") == attrs(
        bgcolor="00ff00",
        blink=True,
        reverse=True,
    )

    # Inline style overrides class
    assert style.get_attrs_for_style_str("#ff0000") == attrs(
        color="ff0000",
    )

    assert style.get_attrs_for_style_str("class:a #00ff00") == attrs(
        color="00ff00",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
    )

    assert style.get_attrs_for_style_str("#00ff00 class:a") == attrs(
        color="ff0000",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
    )


def test_class_combinations_1():
    style = Style(
        [
            ("a", "#0000ff"),
            ("b", "#00ff00"),
            ("a b", "#ff0000"),
        ]
    )

    expected = attrs(color="ff0000")

    for s in [
        "class:a class:b",
        "class:a,b",
        "class:a,b,c",
        "class:b class:a",
        "class:b,a",
    ]:
        assert style.get_attrs_for_style_str(s) == expected


def test_class_combinations_2():
    style = Style(
        [
            ("a b", "#ff0000"),
            ("b", "#00ff00"),
            ("a", "#0000ff"),
        ]
    )

    assert style.get_attrs_for_style_str("class:a class:b") == attrs(color="00ff00")
    assert style.get_attrs_for_style_str("class:a,b") == attrs(color="00ff00")
    assert style.get_attrs_for_style_str("class:a,b,c") == attrs(color="00ff00")

    assert style.get_attrs_for_style_str("class:b class:a") == attrs(color="0000ff")
    assert style.get_attrs_for_style_str("class:b,a") == attrs(color="0000ff")


def test_substyles():
    style = Style(
        [
            ("a.b", "#ff0000 bold"),
            ("a", "#0000ff"),
            ("b", "#00ff00"),
            ("b.c", "#0000ff italic"),
        ]
    )

    assert style.get_attrs_for_style_str("class:a") == attrs(color="0000ff")
    assert style.get_attrs_for_style_str("class:a.b") == attrs(
        color="ff0000",
        bold=True,
    )
    assert style.get_attrs_for_style_str("class:a.b.c") == attrs(
        color="ff0000",
        bold=True,
    )

    assert style.get_attrs_for_style_str("class:b") == attrs(color="00ff00")
    assert style.get_attrs_for_style_str("class:b.a") == attrs(color="00ff00")

    assert style.get_attrs_for_style_str("class:b.c") == attrs(
        color="0000ff",
        italic=True,
    )
    assert style.get_attrs_for_style_str("class:b.c.d") == attrs(
        color="0000ff",
        italic=True,
    )


def test_swap_light_and_dark_style_transformation():
    transformation = SwapLightAndDarkStyleTransformation()

    before = Attrs(
        color="440000",
        bgcolor="888844",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
        blink=False,
        reverse=False,
        hidden=False,
        dim=False,
    )

    after = Attrs(
        color="ffbbbb",
        bgcolor="bbbb76",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
        blink=False,
        reverse=False,
        hidden=False,
        dim=False,
    )

    assert transformation.transform_attrs(before) == after

    before = Attrs(
        color="ansired",
        bgcolor="ansiblack",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
        blink=False,
        reverse=False,
        hidden=False,
        dim=False,
    )

    after = Attrs(
        color="ansibrightred",
        bgcolor="ansiwhite",
        bold=True,
        underline=True,
        strike=True,
        italic=True,
        blink=False,
        reverse=False,
        hidden=False,
        dim=False,
    )

    assert transformation.transform_attrs(before) == after
