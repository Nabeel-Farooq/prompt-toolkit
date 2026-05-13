"""
Tools for creating styles from dictionaries.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Hashable
from enum import Enum
from typing import TypeVar

from prompt_toolkit.cache import SimpleCache

from .base import (
    ANSI_COLOR_NAMES,
    ANSI_COLOR_NAMES_ALIASES,
    DEFAULT_ATTRS,
    Attrs,
    BaseStyle,
)
from .named_colors import NAMED_COLORS

__all__ = [
    "Style",
    "parse_color",
    "Priority",
    "merge_styles",
]


_named_colors_lowercase = {
    key.lower(): value.lstrip("#")
    for key, value in NAMED_COLORS.items()
}


def parse_color(text: str) -> str:
    """
    Parse and validate a color string.

    Supports:
    - ANSI color names
    - Named CSS colors
    - 3/6 digit hex colors
    - "default" / empty string
    """
    if not text:
        return ""

    # ANSI colors.
    if text in ANSI_COLOR_NAMES:
        return text

    alias = ANSI_COLOR_NAMES_ALIASES.get(text)

    if alias is not None:
        return alias

    # Named colors.
    named = _named_colors_lowercase.get(text.lower())

    if named is not None:
        return named

    # Hex colors.
    if text.startswith("#"):
        col = text[1:]

        if col in ANSI_COLOR_NAMES:
            return col

        alias = ANSI_COLOR_NAMES_ALIASES.get(col)

        if alias is not None:
            return alias

        if len(col) == 6:
            return col

        if len(col) == 3:
            return "".join(char * 2 for char in col)

    elif text == "default":
        return text

    raise ValueError(f"Wrong color format {text!r}")


# Attributes with undefined values.
_EMPTY_ATTRS = Attrs(
    color=None,
    bgcolor=None,
    bold=None,
    underline=None,
    strike=None,
    italic=None,
    blink=None,
    reverse=None,
    hidden=None,
    dim=None,
)


def _expand_classname(classname: str) -> list[str]:
    """
    Expand hierarchical class names.

    Example:
        "a.b.c" -> ["a", "a.b", "a.b.c"]
    """
    parts = classname.split(".")

    return [
        ".".join(parts[:index]).lower()
        for index in range(1, len(parts) + 1)
    ]


def _parse_style_str(style_str: str) -> Attrs:
    """
    Parse a style string into an :class:`Attrs` object.
    """
    attrs = DEFAULT_ATTRS if "noinherit" in style_str else _EMPTY_ATTRS

    replacements = {
        "bold": ("bold", True),
        "nobold": ("bold", False),
        "italic": ("italic", True),
        "noitalic": ("italic", False),
        "underline": ("underline", True),
        "nounderline": ("underline", False),
        "strike": ("strike", True),
        "nostrike": ("strike", False),
        "blink": ("blink", True),
        "noblink": ("blink", False),
        "reverse": ("reverse", True),
        "noreverse": ("reverse", False),
        "hidden": ("hidden", True),
        "nohidden": ("hidden", False),
        "dim": ("dim", True),
        "nodim": ("dim", False),
    }

    ignored_parts = {
        "roman",
        "sans",
        "mono",
    }

    for part in style_str.split():
        if part == "noinherit":
            continue

        replacement = replacements.get(part)

        if replacement is not None:
            field, value = replacement
            attrs = attrs._replace(**{field: value})
            continue

        # Ignored pygments properties.
        if part in ignored_parts or part.startswith("border:"):
            continue

        # Ignore internal metadata.
        if part.startswith("[") and part.endswith("]"):
            continue

        # Background color.
        if part.startswith("bg:"):
            attrs = attrs._replace(
                bgcolor=parse_color(part[3:])
            )
            continue

        # Foreground color.
        if part.startswith("fg:"):
            attrs = attrs._replace(
                color=parse_color(part[3:])
            )
            continue

        # Shorthand foreground color.
        attrs = attrs._replace(color=parse_color(part))

    return attrs


CLASS_NAMES_RE = re.compile(r"^[a-z0-9.\s_-]*$")


class Priority(Enum):
    """
    Style rule priority strategy.
    """

    DICT_KEY_ORDER = "KEY_ORDER"
    MOST_PRECISE = "MOST_PRECISE"


default_priority = Priority.DICT_KEY_ORDER


class Style(BaseStyle):
    """
    Style implementation based on style rules.
    """

    __slots__ = (
        "_style_rules",
        "class_names_and_attrs",
    )

    def __init__(
        self,
        style_rules: list[tuple[str, str]],
    ) -> None:
        class_names_and_attrs: list[
            tuple[frozenset[str], Attrs]
        ] = []

        for class_names, style_str in style_rules:
            if not CLASS_NAMES_RE.match(class_names):
                raise ValueError(repr(class_names))

            attrs = _parse_style_str(style_str)

            class_names_and_attrs.append(
                (
                    frozenset(class_names.lower().split()),
                    attrs,
                )
            )

        self._style_rules = style_rules
        self.class_names_and_attrs = class_names_and_attrs

    @property
    def style_rules(self) -> list[tuple[str, str]]:
        return self._style_rules

    @classmethod
    def from_dict(
        cls,
        style_dict: dict[str, str],
        priority: Priority = default_priority,
    ) -> Style:
        """
        Create a style from a dictionary.
        """
        if priority == Priority.MOST_PRECISE:

            def key(item: tuple[str, str]) -> int:
                return sum(
                    len(part.split("."))
                    for part in item[0].split()
                )

            return cls(
                sorted(
                    style_dict.items(),
                    key=key,
                )
            )

        return cls(list(style_dict.items()))

    def get_attrs_for_style_str(
        self,
        style_str: str,
        default: Attrs = DEFAULT_ATTRS,
    ) -> Attrs:
        """
        Resolve attributes for a style string.
        """
        list_of_attrs: list[Attrs] = [default]

        class_names: set[str] = set()

        # Apply global/default rules.
        for names, attr in self.class_names_and_attrs:
            if not names:
                list_of_attrs.append(attr)

        for part in style_str.split():
            if part.startswith("class:"):
                new_class_names: list[str] = []

                for item in part[6:].lower().split(","):
                    new_class_names.extend(
                        _expand_classname(item)
                    )

                for new_name in new_class_names:
                    combos = {
                        frozenset([new_name]),
                    }

                    for count in range(
                        1,
                        len(class_names) + 1,
                    ):
                        combos.update(
                            frozenset(combo + (new_name,))
                            for combo in itertools.combinations(
                                class_names,
                                count,
                            )
                        )

                    for names, attr in self.class_names_and_attrs:
                        if names in combos:
                            list_of_attrs.append(attr)

                    class_names.add(new_name)

            else:
                list_of_attrs.append(
                    _parse_style_str(part)
                )

        return _merge_attrs(list_of_attrs)

    def invalidation_hash(self) -> Hashable:
        return id(self.class_names_and_attrs)


_T = TypeVar("_T")


def _merge_attrs(list_of_attrs: list[Attrs]) -> Attrs:
    """
    Merge multiple :class:`Attrs` objects.
    """

    def _or(*values: _T) -> _T:
        """
        Return the last non-None value.
        """
        for value in reversed(values):
            if value is not None:
                return value

        raise ValueError(
            "Expected at least one non-None value."
        )

    return Attrs(
        color=_or(
            "",
            *(attr.color for attr in list_of_attrs),
        ),
        bgcolor=_or(
            "",
            *(attr.bgcolor for attr in list_of_attrs),
        ),
        bold=_or(
            False,
            *(attr.bold for attr in list_of_attrs),
        ),
        underline=_or(
            False,
            *(attr.underline for attr in list_of_attrs),
        ),
        strike=_or(
            False,
            *(attr.strike for attr in list_of_attrs),
        ),
        italic=_or(
            False,
            *(attr.italic for attr in list_of_attrs),
        ),
        blink=_or(
            False,
            *(attr.blink for attr in list_of_attrs),
        ),
        reverse=_or(
            False,
            *(attr.reverse for attr in list_of_attrs),
        ),
        hidden=_or(
            False,
            *(attr.hidden for attr in list_of_attrs),
        ),
        dim=_or(
            False,
            *(attr.dim for attr in list_of_attrs),
        ),
    )


def merge_styles(
    styles: list[BaseStyle],
) -> _MergedStyle:
    """
    Merge multiple styles into one.
    """
    return _MergedStyle(
        [style for style in styles if style is not None]
    )


class _MergedStyle(BaseStyle):
    """
    Dynamically merged style wrapper.
    """

    __slots__ = (
        "styles",
        "_style",
    )

    def __init__(
        self,
        styles: list[BaseStyle],
    ) -> None:
        self.styles = styles

        self._style: SimpleCache[
            Hashable,
            Style,
        ] = SimpleCache(maxsize=1)

    @property
    def _merged_style(self) -> Style:
        """
        Cached merged style instance.
        """

        def get() -> Style:
            return Style(self.style_rules)

        return self._style.get(
            self.invalidation_hash(),
            get,
        )

    @property
    def style_rules(self) -> list[tuple[str, str]]:
        style_rules: list[tuple[str, str]] = []

        for style in self.styles:
            style_rules.extend(style.style_rules)

        return style_rules

    def get_attrs_for_style_str(
        self,
        style_str: str,
        default: Attrs = DEFAULT_ATTRS,
    ) -> Attrs:
        return self._merged_style.get_attrs_for_style_str(
            style_str,
            default,
        )

    def invalidation_hash(self) -> Hashable:
        return tuple(
            style.invalidation_hash()
            for style in self.styles
        )
