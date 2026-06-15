from __future__ import annotations

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.contrib.regular_languages import compile
from prompt_toolkit.contrib.regular_languages.compiler import Match, Variables
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.document import Document


def test_simple_match():
    g = compile("hello|world")

    assert isinstance(g.match("hello"), Match)
    assert isinstance(g.match("world"), Match)
    assert g.match("somethingelse") is None


def test_variable_varname():
    """
    Test `Variable` with varname.
    """
    g = compile("((?P<varname>hello|world)|test)")

    m = g.match("hello")
    variables = m.variables()
    assert isinstance(variables, Variables)
    assert variables.get("varname") == "hello"
    assert variables["varname"] == "hello"

    m = g.match("world")
    variables = m.variables()
    assert isinstance(variables, Variables)
    assert variables.get("varname") == "world"
    assert variables["varname"] == "world"

    m = g.match("test")
    variables = m.variables()
    assert isinstance(variables, Variables)
    assert variables.get("varname") is None
    assert variables["varname"] is None


def test_prefix():
    """
    Test `match_prefix`.
    """
    g = compile(r"(hello\ world|something\ else)")

    for text in (
        "hello world",
        "he",
        "",
        "som",
        "hello wor",
    ):
        assert isinstance(g.match_prefix(text), Match)

    m = g.match_prefix("no-match")
    assert m.trailing_input().start == 0
    assert m.trailing_input().stop == len("no-match")

    text = "hellotest"
    m = g.match_prefix(text)
    assert m.trailing_input().start == len("hello")
    assert m.trailing_input().stop == len(text)


def test_completer():
    class completer1(Completer):
        def get_completions(self, document, complete_event):
            text = document.text
            start_position = -len(text)

            yield Completion(
                f"before-{text}-after",
                start_position,
            )
            yield Completion(
                f"before-{text}-after-B",
                start_position,
            )

    class completer2(Completer):
        def get_completions(self, document, complete_event):
            text = document.text
            start_position = -len(text)

            yield Completion(
                f"before2-{text}-after2",
                start_position,
            )
            yield Completion(
                f"before2-{text}-after2-B",
                start_position,
            )

    # Create grammar. "var1" + "whitespace" + "var2"
    g = compile(r"(?P<var1>[a-z]*) \s+ (?P<var2>[a-z]*)")

    completer = GrammarCompleter(
        g,
        {
            "var1": completer1(),
            "var2": completer2(),
        },
    )

    text = "abc def"
    completions = list(
        completer.get_completions(
            Document(text, len(text)),
            CompleteEvent(),
        )
    )

    assert len(completions) == 2

    completion = completions[0]
    assert completion.text == "before2-def-after2"
    assert completion.start_position == -3

    completion = completions[1]
    assert completion.text == "before2-def-after2-B"
    assert completion.start_position == -3
