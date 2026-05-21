from __future__ import annotations

import re

import pytest

from prompt_toolkit.document import Document


@pytest.fixture
def document() -> Document:
    text = (
        "line 1\n"
        "line 2\n"
        "line 3\n"
        "line 4\n"
    )

    cursor_position = len("line 1\nlin")

    return Document(
        text=text,
        cursor_position=cursor_position,
    )


def test_current_char(document: Document) -> None:
    assert document.current_char == "e"
    assert document.char_before_cursor == "n"


def test_text_before_cursor(document: Document) -> None:
    assert document.text_before_cursor == "line 1\nlin"


def test_text_after_cursor(document: Document) -> None:
    expected = (
        "e 2\n"
        "line 3\n"
        "line 4\n"
    )

    assert document.text_after_cursor == expected


def test_lines(document: Document) -> None:
    assert document.lines == [
        "line 1",
        "line 2",
        "line 3",
        "line 4",
        "",
    ]


def test_line_count(document: Document) -> None:
    assert document.line_count == 5


def test_current_line_before_cursor(
    document: Document,
) -> None:
    assert document.current_line_before_cursor == "lin"


def test_current_line_after_cursor(
    document: Document,
) -> None:
    assert document.current_line_after_cursor == "e 2"


def test_current_line(document: Document) -> None:
    assert document.current_line == "line 2"


def test_cursor_position(document: Document) -> None:
    assert document.cursor_position_row == 1
    assert document.cursor_position_col == 3

    empty_document = Document("", 0)

    assert empty_document.cursor_position_row == 0
    assert empty_document.cursor_position_col == 0


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (
            len("line 1\nline 2\nlin"),
            (2, 3),
        ),
        (
            0,
            (0, 0),
        ),
    ],
)
def test_translate_index_to_position(
    document: Document,
    index: int,
    expected: tuple[int, int],
) -> None:
    assert (
        document.translate_index_to_position(index)
        == expected
    )


@pytest.mark.parametrize(
    ("text", "cursor", "expected"),
    [
        ("hello", 5, True),
        ("hello", 4, False),
    ],
)
def test_is_cursor_at_the_end(
    text: str,
    cursor: int,
    expected: bool,
) -> None:
    document = Document(text, cursor)

    assert document.is_cursor_at_the_end is expected


def test_get_word_before_cursor_with_whitespace() -> None:
    text = "foobar "

    document = Document(
        text=text,
        cursor_position=len(text),
    )

    assert document.get_word_before_cursor() == ""


def test_get_word_before_cursor_with_pattern() -> None:
    text = "foobar "

    document = Document(
        text=text,
        cursor_position=len(text),
    )

    find_word_re = re.compile(
        r"([a-zA-Z0-9_]+|[^a-zA-Z0-9_\s]+)"
    )

    assert (
        document.get_word_before_cursor(
            pattern=find_word_re
        )
        == ""
    )


def test_empty_document_behavior() -> None:
    document = Document("", 0)

    assert document.text == ""
    assert document.lines == [""]
    assert document.current_line == ""
    assert document.current_char == ""
    assert document.char_before_cursor == ""


def test_cursor_position_at_start() -> None:
    document = Document(
        text="hello world",
        cursor_position=0,
    )

    assert document.current_char == "h"
    assert document.char_before_cursor == ""
    assert document.text_before_cursor == ""


if __name__ == "__main__":
    pytest.main([__file__])
