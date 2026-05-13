"""
Base classes and utilities for styling.
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Hashable
from typing import NamedTuple

__all__ = [
    "Attrs",
    "DEFAULT_ATTRS",
    "ANSI_COLOR_NAMES",
    "ANSI_COLOR_NAMES_ALIASES",
    "BaseStyle",
    "DummyStyle",
    "DynamicStyle",
]


class Attrs(NamedTuple):
    """
    Style attributes.

    :param color:
        Hexadecimal foreground color or ANSI color name.
    :param bgcolor:
        Hexadecimal background color or ANSI color name.
    :param bold:
        Bold text.
    :param underline:
        Underlined text.
    :param strike:
        Strikethrough text.
    :param italic:
        Italic text.
    :param blink:
        Blinking text.
    :param reverse:
        Reverse foreground/background colors.
    :param hidden:
        Hidden text.
    :param dim:
        Dimmed text.
    """

    color: str | None
    bgcolor: str | None
    bold: bool | None
    underline: bool | None
    strike: bool | None
    italic: bool | None
    blink: bool | None
    reverse: bool | None
    hidden: bool | None
    dim: bool | None


#: Default attribute set.
DEFAULT_ATTRS = Attrs(
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


#: Supported ANSI color names.
ANSI_COLOR_NAMES = [
    "ansidefault",
    # Low intensity colors.
    "ansiblack",
    "ansired",
    "ansigreen",
    "ansiyellow",
    "ansiblue",
    "ansimagenta",
    "ansicyan",
    "ansigray",
    # Bright colors.
    "ansibrightblack",
    "ansibrightred",
    "ansibrightgreen",
    "ansibrightyellow",
    "ansibrightblue",
    "ansibrightmagenta",
    "ansibrightcyan",
    "ansiwhite",
]


#: Legacy ANSI color aliases.
ANSI_COLOR_NAMES_ALIASES: dict[str, str] = {
    "ansidarkgray": "ansibrightblack",
    "ansiteal": "ansicyan",
    "ansiturquoise": "ansibrightcyan",
    "ansibrown": "ansiyellow",
    "ansipurple": "ansimagenta",
    "ansifuchsia": "ansibrightmagenta",
    "ansilightgray": "ansigray",
    "ansidarkred": "ansired",
    "ansidarkgreen": "ansigreen",
    "ansidarkblue": "ansiblue",
}

assert set(ANSI_COLOR_NAMES_ALIASES.values()).issubset(
    ANSI_COLOR_NAMES
)

assert not (
    set(ANSI_COLOR_NAMES_ALIASES) & set(ANSI_COLOR_NAMES)
)


class BaseStyle(metaclass=ABCMeta):
    """
    Abstract base class for prompt_toolkit styles.
    """

    @abstractmethod
    def get_attrs_for_style_str(
        self,
        style_str: str,
        default: Attrs = DEFAULT_ATTRS,
    ) -> Attrs:
        """
        Return :class:`Attrs` for the given style string.

        :param style_str:
            Style definition string.
        :param default:
            Fallback attributes when no style matches.
        """

    @property
    @abstractmethod
    def style_rules(self) -> list[tuple[str, str]]:
        """
        Style rules used to create this style.
        """
        return []

    @abstractmethod
    def invalidation_hash(self) -> Hashable:
        """
        Return a hash used for renderer cache invalidation.
        """


class DummyStyle(BaseStyle):
    """
    Style implementation that applies no styling.
    """

    __slots__ = ()

    def get_attrs_for_style_str(
        self,
        style_str: str,
        default: Attrs = DEFAULT_ATTRS,
    ) -> Attrs:
        return default

    def invalidation_hash(self) -> Hashable:
        """
        Constant invalidation hash.
        """
        return 1

    @property
    def style_rules(self) -> list[tuple[str, str]]:
        return []


class DynamicStyle(BaseStyle):
    """
    Style wrapper that dynamically resolves another style.

    :param get_style:
        Callable returning a :class:`BaseStyle` instance.
    """

    __slots__ = ("get_style", "_dummy")

    def __init__(
        self,
        get_style: Callable[[], BaseStyle | None],
    ) -> None:
        self.get_style = get_style
        self._dummy = DummyStyle()

    def _style(self) -> BaseStyle:
        """
        Return the active style or fallback dummy style.
        """
        return self.get_style() or self._dummy

    def get_attrs_for_style_str(
        self,
        style_str: str,
        default: Attrs = DEFAULT_ATTRS,
    ) -> Attrs:
        return self._style().get_attrs_for_style_str(
            style_str,
            default,
        )

    def invalidation_hash(self) -> Hashable:
        return self._style().invalidation_hash()

    @property
    def style_rules(self) -> list[tuple[str, str]]:
        return self._style().style_rules
