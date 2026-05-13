from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prompt_toolkit.input.base import Input
    from prompt_toolkit.output.base import Output

    from .application import Application

__all__ = [
    "AppSession",
    "get_app_session",
    "get_app",
    "get_app_or_none",
    "set_app",
    "create_app_session",
    "create_app_session_from_tty",
]


class AppSession:
    """
    Interactive application session, usually bound to a single terminal.

    Multiple applications can run sequentially within the same session while
    sharing the same input/output devices.

    Warning:
        Always use `create_app_session()` instead of instantiating this class
        directly so the session is properly activated.

    :param input:
        Default input object used by applications in this session unless
        overridden explicitly.
    :param output:
        Default output object used by applications in this session unless
        overridden explicitly.
    """

    def __init__(
        self,
        input: Input | None = None,
        output: Output | None = None,
    ) -> None:
        self._input = input
        self._output = output

        # Dynamically assigned by `set_app`.
        self.app: Application[Any] | None = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(app={self.app!r})"

    @property
    def input(self) -> Input:
        """
        Lazily create and cache the default input object.
        """
        if self._input is None:
            from prompt_toolkit.input.defaults import create_input

            self._input = create_input()

        return self._input

    @property
    def output(self) -> Output:
        """
        Lazily create and cache the default output object.
        """
        if self._output is None:
            from prompt_toolkit.output.defaults import create_output

            self._output = create_output()

        return self._output


_current_app_session: ContextVar[AppSession] = ContextVar(
    "_current_app_session",
    default=AppSession(),
)


def get_app_session() -> AppSession:
    """
    Return the currently active application session.
    """
    return _current_app_session.get()


def get_app() -> Application[Any]:
    """
    Return the currently active application.

    During `Application.run_async()`, the active application is stored in the
    current `AppSession`.

    If no application is running, a `DummyApplication` instance is returned
    instead of raising an exception.
    """
    session = get_app_session()

    if session.app is not None:
        return session.app

    from .dummy import DummyApplication

    return DummyApplication()


def get_app_or_none() -> Application[Any] | None:
    """
    Return the currently active application or `None`
    when no application is running.
    """
    return get_app_session().app


@contextmanager
def set_app(app: Application[Any]) -> Generator[None, None, None]:
    """
    Temporarily set the given application as active for the current session.

    This should only be called internally by the `Application` itself.

    If application state needs to propagate across threads or coroutines,
    use `contextvars.copy_context()` or `Application.context`.
    """
    session = get_app_session()

    previous_app = session.app
    session.app = app

    try:
        yield
    finally:
        session.app = previous_app


@contextmanager
def create_app_session(
    input: Input | None = None,
    output: Output | None = None,
) -> Generator[AppSession, None, None]:
    """
    Create and activate a separate `AppSession`.

    Useful when multiple independent sessions exist simultaneously,
    such as in Telnet or SSH servers.
    """
    current_session = get_app_session()

    # Reuse already-created input/output objects when available.
    # Avoid forcing lazy initialization on the parent session.
    if input is None:
        input = current_session._input

    if output is None:
        output = current_session._output

    session = AppSession(
        input=input,
        output=output,
    )

    token = _current_app_session.set(session)

    try:
        yield session
    finally:
        _current_app_session.reset(token)


@contextmanager
def create_app_session_from_tty() -> Generator[AppSession, None, None]:
    """
    Create an `AppSession` that always prefers TTY input/output.

    Even if stdin/stdout are redirected through pipes, interaction will still
    happen through the terminal when possible.

    Example:
        from prompt_toolkit.shortcuts import prompt

        with create_app_session_from_tty():
            prompt(">")
    """
    from prompt_toolkit.input.defaults import create_input
    from prompt_toolkit.output.defaults import create_output

    input = create_input(always_prefer_tty=True)
    output = create_output(always_prefer_tty=True)

    with create_app_session(input=input, output=output) as app_session:
        yield app_session
