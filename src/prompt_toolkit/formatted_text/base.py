from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, TypeAlias, Union, cast

from prompt_toolkit.mouse_events import MouseEvent

if TYPE_CHECKING:
    from typing_extensions import Protocol, TypeGuard

    from prompt_toolkit.key_binding.key_bindings import (
        NotImplementedOrNone,
    )

__all__ = [
    "OneStyleAndTextTuple",
    "StyleAndTextTuples",
    "MagicFormattedText",
    "AnyFormattedText",
    "FormattedText",
    "Template",
    "to_formatted_text",
    "is_formatted_text",
    "merge_formatted_text",
]


# ============================================================================
# Types
# ============================================================================


MouseHandler = Callable[[MouseEvent], "NotImplementedOrNone"]


OneStyleAndTextTuple: TypeAlias = (
    tuple[str, str]
    | tuple[str, str, MouseHandler]
)

StyleAndTextTuples: TypeAlias = list[OneStyleAndTextTuple]


if TYPE_CHECKING:

    class MagicFormattedText(Protocol):
        """
        Protocol for objects implementing formatted text conversion.
        """

        def __pt_formatted_text__(self) -> StyleAndTextTuples: ...


AnyFormattedText: TypeAlias = Union[
    str,
    "MagicFormattedText",
    StyleAndTextTuples,
    Callable[[], "AnyFormattedText"],
    None,
]


# ============================================================================
# Helpers
# ============================================================================


def _apply_style(
    fragments: StyleAndTextTuples,
    style: str,
) -> StyleAndTextTuples:
    """
    Apply an additional style string to all fragments.
    """
    if not style:
        return fragments

    return cast(
        StyleAndTextTuples,
        [
            (
                f"{style} {fragment_style}".strip(),
                *rest,
            )
            for fragment_style, *rest in fragments
        ],
    )


def _ensure_formatted_text(
    value: FormattedText | StyleAndTextTuples,
) -> FormattedText:
    """
    Ensure result is wrapped in `FormattedText`.
    """
    if isinstance(value, FormattedText):
        return value

    return FormattedText(value)


# ============================================================================
# Conversion
# ============================================================================


def to_formatted_text(
    value: AnyFormattedText,
    style: str = "",
    auto_convert: bool = False,
) -> FormattedText:
    """
    Convert any supported formatted text object into `FormattedText`.

    Supported values:
        - Plain strings
        - `FormattedText`
        - Lists of fragments
        - Objects implementing `__pt_formatted_text__`
        - Zero-argument callables returning formatted text
        - `None`

    :param style:
        Additional style string applied to all fragments.

    :param auto_convert:
        When `True`, unsupported values are converted using `str()`.
    """
    result: FormattedText | StyleAndTextTuples

    if value is None:
        result = []

    elif isinstance(value, str):
        result = [("", value)]

    elif isinstance(value, list):
        result = value

    elif hasattr(value, "__pt_formatted_text__"):
        result = cast(
            "MagicFormattedText",
            value,
        ).__pt_formatted_text__()

    elif callable(value):
        return to_formatted_text(
            value(),
            style=style,
            auto_convert=auto_convert,
        )

    elif auto_convert:
        result = [("", str(value))]

    else:
        raise ValueError(
            "Expected formatted text, plain string, or object "
            f"implementing '__pt_formatted_text__'. Got: {value!r}"
        )

    return _ensure_formatted_text(
        _apply_style(result, style),
    )


# ============================================================================
# Validation
# ============================================================================


def is_formatted_text(
    value: object,
) -> TypeGuard[AnyFormattedText]:
    """
    Return whether the value is accepted as formatted text.

    Note:
        Callables are accepted without validating their return type.
    """
    return (
        callable(value)
        or isinstance(value, (str, list))
        or hasattr(value, "__pt_formatted_text__")
    )


# ============================================================================
# Formatted text container
# ============================================================================


class FormattedText(StyleAndTextTuples):
    """
    Canonical formatted text container.

    Stores a list of:
        - `(style, text)`
        - `(style, text, mouse_handler)`
    tuples.
    """

    def __pt_formatted_text__(self) -> StyleAndTextTuples:
        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self)!r})"


# ============================================================================
# Template
# ============================================================================


class Template:
    """
    Template helper for formatted text interpolation.

    Example:
        ```python
        Template("Hello {}").format(HTML("<b>world</b>"))
        ```
    """

    def __init__(self, text: str) -> None:
        if "{0}" in text:
            raise ValueError(
                "Positional formatting is not supported."
            )

        self.text = text

    def format(
        self,
        *values: AnyFormattedText,
    ) -> Callable[[], FormattedText]:
        """
        Create lazily evaluated formatted text.
        """

        def build() -> FormattedText:
            parts = self.text.split("{}")

            if len(parts) - 1 != len(values):
                raise ValueError(
                    "Template placeholder count does not match "
                    "number of values."
                )

            result = FormattedText()

            for part, value in zip(parts, values):
                result.append(("", part))
                result.extend(to_formatted_text(value))

            result.append(("", parts[-1]))

            return result

        return build


# ============================================================================
# Merge helpers
# ============================================================================


def merge_formatted_text(
    items: Iterable[AnyFormattedText],
) -> Callable[[], FormattedText]:
    """
    Concatenate multiple formatted text objects.
    """

    def build() -> FormattedText:
        result = FormattedText()

        for item in items:
            result.extend(to_formatted_text(item))

        return result

    return build
