"""
Input validation for a `Buffer`.
(Validators will be called before accepting input.)
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Callable

from prompt_toolkit.eventloop import run_in_executor_with_context

from .document import Document
from .filters import FilterOrBool, to_filter

__all__ = [
    "ConditionalValidator",
    "ValidationError",
    "Validator",
    "ThreadedValidator",
    "DummyValidator",
    "DynamicValidator",
]


class ValidationError(Exception):
    """
    Error raised by :meth:`.Validator.validate`.

    :param cursor_position: The cursor position where the error occurred.
    :param message: Text.
    """

    __slots__ = ("cursor_position", "message")

    def __init__(self, cursor_position: int = 0, message: str = "") -> None:
        super().__init__(message)
        self.cursor_position = cursor_position
        self.message = message

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"cursor_position={self.cursor_position!r}, "
            f"message={self.message!r})"
        )


class Validator(metaclass=ABCMeta):
    """
    Abstract base class for an input validator.

    A validator is typically created in one of the following two ways:

    - Either by overriding this class and implementing the `validate` method.
    - Or by passing a callable to `Validator.from_callable`.

    If the validation takes some time and needs to happen in a background
    thread, this can be wrapped in a :class:`.ThreadedValidator`.
    """

    @abstractmethod
    def validate(self, document: Document) -> None:
        """
        Validate the input.
        If invalid, this should raise a :class:`.ValidationError`.

        :param document: :class:`~prompt_toolkit.document.Document` instance.
        """

    async def validate_async(self, document: Document) -> None:
        """
        Return a `Future` which is set when the validation is ready.
        This function can be overloaded in order to provide an asynchronous
        implementation.
        """
        self.validate(document)

    @classmethod
    def from_callable(
        cls,
        validate_func: Callable[[str], bool],
        error_message: str = "Invalid input",
        move_cursor_to_end: bool = False,
    ) -> Validator:
        """
        Create a validator from a simple validate callable. E.g.:

        .. code:: python

            def is_valid(text):
                return text in ['hello', 'world']
            Validator.from_callable(is_valid, error_message='Invalid input')

        :param validate_func: Callable that takes the input string, and returns
            `True` if the input is valid input.
        :param error_message: Message to be displayed if the input is invalid.
        :param move_cursor_to_end: Move the cursor to the end of the input, if
            the input is invalid.
        """
        return _ValidatorFromCallable(
            validate_func,
            error_message,
            move_cursor_to_end,
        )


class _ValidatorFromCallable(Validator):
    """
    Validate input from a simple callable.
    """

    __slots__ = ("func", "error_message", "move_cursor_to_end")

    def __init__(
        self,
        func: Callable[[str], bool],
        error_message: str,
        move_cursor_to_end: bool,
    ) -> None:
        self.func = func
        self.error_message = error_message
        self.move_cursor_to_end = move_cursor_to_end

    def __repr__(self) -> str:
        return f"Validator.from_callable({self.func!r})"

    def validate(self, document: Document) -> None:
        if self.func(document.text):
            return

        raise ValidationError(
            cursor_position=len(document.text) if self.move_cursor_to_end else 0,
            message=self.error_message,
        )


class ThreadedValidator(Validator):
    """
    Wrapper that runs input validation in a thread.
    (Use this to prevent the user interface from becoming unresponsive if the
    input validation takes too much time.)
    """

    __slots__ = ("validator",)

    def __init__(self, validator: Validator) -> None:
        self.validator = validator

    def validate(self, document: Document) -> None:
        self.validator.validate(document)

    async def validate_async(self, document: Document) -> None:
        """
        Run the `validate` function in a thread.
        """
        await run_in_executor_with_context(lambda: self.validate(document))


class DummyValidator(Validator):
    """
    Validator class that accepts any input.
    """

    def validate(self, document: Document) -> None:
        pass


class ConditionalValidator(Validator):
    """
    Validator that can be switched on/off according to
    a filter. (This wraps around another validator.)
    """

    __slots__ = ("validator", "filter")

    def __init__(self, validator: Validator, filter: FilterOrBool) -> None:
        self.validator = validator
        self.filter = to_filter(filter)

    def validate(self, document: Document) -> None:
        if self.filter():
            self.validator.validate(document)


class DynamicValidator(Validator):
    """
    Validator class that can dynamically returns any Validator.

    :param get_validator: Callable that returns a :class:`.Validator` instance.
    """

    __slots__ = ("get_validator",)

    def __init__(self, get_validator: Callable[[], Validator | None]) -> None:
        self.get_validator = get_validator

    def validate(self, document: Document) -> None:
        (self.get_validator() or DummyValidator()).validate(document)

    async def validate_async(self, document: Document) -> None:
        await (self.get_validator() or DummyValidator()).validate_async(document)
