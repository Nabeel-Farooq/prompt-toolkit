from __future__ import annotations

from typing import Final

from prompt_toolkit.completion.filesystem import (
    ExecutableCompleter,
    PathCompleter,
)
from prompt_toolkit.contrib.regular_languages.compiler import compile
from prompt_toolkit.contrib.regular_languages.completion import (
    GrammarCompleter,
)

__all__ = ["SystemCompleter"]


# ============================================================================
# Grammar
# ============================================================================

_SYSTEM_GRAMMAR: Final[str] = r"""
    # Executable command.
    (?P<executable>[^\s]+)

    # Ignore intermediate arguments.
    (
        \s+
        ("[^"]*" | '[^']*' | [^'"]+ )
    )*

    \s+

    # File path argument.
    (
        (?P<filename>[^\s]+) |
        "(?P<double_quoted_filename>[^\s]+)" |
        '(?P<single_quoted_filename>[^\s]+)'
    )
"""


# ============================================================================
# Escape helpers
# ============================================================================


def _escape_double_quotes(value: str) -> str:
    """Escape double quotes inside a quoted filename."""
    return value.replace('"', '\\"')


def _escape_single_quotes(value: str) -> str:
    """Escape single quotes inside a quoted filename."""
    return value.replace("'", "\\'")


def _unescape_double_quotes(value: str) -> str:
    """
    Unescape double-quoted filename content.

    Note:
        This intentionally handles only basic escaping.
    """
    return value.replace('\\"', '"')


def _unescape_single_quotes(value: str) -> str:
    """
    Unescape single-quoted filename content.

    Note:
        This intentionally handles only basic escaping.
    """
    return value.replace("\\'", "'")


# ============================================================================
# Completer
# ============================================================================


class SystemCompleter(GrammarCompleter):
    """
    Completion engine for shell-like system commands.

    Features:
        - Executable completion.
        - File path completion.
        - Support for quoted filenames.
        - `~` expansion support.
    """

    def __init__(self) -> None:
        grammar = compile(
            _SYSTEM_GRAMMAR,
            escape_funcs={
                "double_quoted_filename": _escape_double_quotes,
                "single_quoted_filename": _escape_single_quotes,
            },
            unescape_funcs={
                "double_quoted_filename": _unescape_double_quotes,
                "single_quoted_filename": _unescape_single_quotes,
            },
        )

        path_completer = PathCompleter(
            only_directories=False,
            expanduser=True,
        )

        super().__init__(
            grammar,
            {
                "executable": ExecutableCompleter(),
                "filename": path_completer,
                "double_quoted_filename": path_completer,
                "single_quoted_filename": path_completer,
            },
        )
