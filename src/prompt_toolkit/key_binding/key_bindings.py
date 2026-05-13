"""
Key bindings registry.

A `KeyBindings` object stores key bindings in an efficient structure for
matching pressed key sequences.

Typical usage::

    kb = KeyBindings()

    @kb.add(Keys.ControlX, Keys.ControlC, filter=INSERT)
    def handler(event):
        pass

Multiple `KeyBindings` objects can be merged together using
`merge_key_bindings`.

`ConditionalKeyBindings` can enable/disable groups of bindings dynamically.

It is also possible to define a binding before assigning keys::

    @key_binding(filter=condition)
    def my_key_binding(event):
        ...

    kb.add(Keys.A, my_key_binding)
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Coroutine, Hashable, Sequence
from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    Union,
    cast,
)

from prompt_toolkit.cache import SimpleCache
from prompt_toolkit.filters import FilterOrBool, Never, to_filter
from prompt_toolkit.keys import KEY_ALIASES, Keys

if TYPE_CHECKING:
    from .key_processor import KeyPressEvent

    NotImplementedOrNone = object


__all__ = [
    "NotImplementedOrNone",
    "Binding",
    "KeyBindingsBase",
    "KeyBindings",
    "ConditionalKeyBindings",
    "merge_key_bindings",
    "DynamicKeyBindings",
    "GlobalOnlyKeyBindings",
]


KeyHandlerCallable = Callable[
    ["KeyPressEvent"],
    Union[
        "NotImplementedOrNone",
        Coroutine[Any, Any, "NotImplementedOrNone"],
    ],
]

KeysTuple = tuple[Keys | str, ...]


class Binding:
    """
    Immutable key binding definition.

    :param record_in_macro:
        When `False`, exclude this binding from macro recording.
    """

    __slots__ = (
        "keys",
        "handler",
        "filter",
        "eager",
        "is_global",
        "save_before",
        "record_in_macro",
    )

    def __init__(
        self,
        keys: KeysTuple,
        handler: KeyHandlerCallable,
        filter: FilterOrBool = True,
        eager: FilterOrBool = False,
        is_global: FilterOrBool = False,
        save_before: Callable[[KeyPressEvent], bool] = lambda e: True,
        record_in_macro: FilterOrBool = True,
    ) -> None:
        self.keys = keys
        self.handler = handler
        self.filter = to_filter(filter)
        self.eager = to_filter(eager)
        self.is_global = to_filter(is_global)
        self.save_before = save_before
        self.record_in_macro = to_filter(record_in_macro)

    def call(self, event: KeyPressEvent) -> None:
        """
        Execute this binding handler.
        """
        result = self.handler(event)

        if isawaitable(result):
            awaitable = cast(
                Coroutine[Any, Any, "NotImplementedOrNone"],
                result,
            )

            async def bg_task() -> None:
                result = await awaitable

                if result is not NotImplemented:
                    event.app.invalidate()

            event.app.create_background_task(bg_task())

        elif result is not NotImplemented:
            event.app.invalidate()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"keys={self.keys!r}, handler={self.handler!r})"
        )


class KeyBindingsBase(metaclass=ABCMeta):
    """
    Abstract interface for key bindings collections.
    """

    @property
    @abstractmethod
    def _version(self) -> Hashable:
        """
        Version identifier used for cache invalidation.
        """
        return 0

    @abstractmethod
    def get_bindings_for_keys(self, keys: KeysTuple) -> list[Binding]:
        """
        Return bindings matching the given key sequence.
        """
        return []

    @abstractmethod
    def get_bindings_starting_with_keys(
        self,
        keys: KeysTuple,
    ) -> list[Binding]:
        """
        Return bindings whose sequences start with `keys`.
        """
        return []

    @property
    @abstractmethod
    def bindings(self) -> list[Binding]:
        """
        List of bindings.
        """
        return []


T = TypeVar("T", bound=KeyHandlerCallable | Binding)


class KeyBindings(KeyBindingsBase):
    """
    Container for key bindings.
    """

    def __init__(self) -> None:
        self._bindings: list[Binding] = []

        self._get_bindings_for_keys_cache: SimpleCache[
            KeysTuple,
            list[Binding],
        ] = SimpleCache(maxsize=10000)

        self._get_bindings_starting_with_keys_cache: SimpleCache[
            KeysTuple,
            list[Binding],
        ] = SimpleCache(maxsize=1000)

        self.__version = 0

    def _clear_cache(self) -> None:
        """
        Invalidate internal caches.
        """
        self.__version += 1

        self._get_bindings_for_keys_cache.clear()
        self._get_bindings_starting_with_keys_cache.clear()

    @property
    def bindings(self) -> list[Binding]:
        return self._bindings

    @property
    def _version(self) -> Hashable:
        return self.__version

    def add(
        self,
        *keys: Keys | str,
        filter: FilterOrBool = True,
        eager: FilterOrBool = False,
        is_global: FilterOrBool = False,
        save_before: Callable[[KeyPressEvent], bool] = lambda e: True,
        record_in_macro: FilterOrBool = True,
    ) -> Callable[[T], T]:
        """
        Decorator for registering a key binding.
        """
        if not keys:
            raise ValueError("At least one key must be provided.")

        parsed_keys = tuple(_parse_key(k) for k in keys)

        if isinstance(filter, Never):

            def decorator(func: T) -> T:
                return func

            return decorator

        filter_obj = to_filter(filter)
        eager_obj = to_filter(eager)
        global_obj = to_filter(is_global)
        macro_obj = to_filter(record_in_macro)

        def decorator(func: T) -> T:
            if isinstance(func, Binding):
                binding = Binding(
                    parsed_keys,
                    func.handler,
                    filter=func.filter & filter_obj,
                    eager=eager_obj | func.eager,
                    is_global=global_obj | func.is_global,
                    save_before=func.save_before,
                    record_in_macro=func.record_in_macro,
                )

            else:
                binding = Binding(
                    parsed_keys,
                    cast(KeyHandlerCallable, func),
                    filter=filter_obj,
                    eager=eager_obj,
                    is_global=global_obj,
                    save_before=save_before,
                    record_in_macro=macro_obj,
                )

            self.bindings.append(binding)
            self._clear_cache()

            return func

        return decorator

    def remove(self, *args: Keys | str | KeyHandlerCallable) -> None:
        """
        Remove a key binding by handler or key sequence.
        """
        found = False
        function: Any = None

        if callable(args[0]):
            if len(args) != 1:
                raise ValueError(
                    "Removing by callable accepts exactly one argument."
                )

            function = args[0]

            bindings_to_remove = [
                b for b in self.bindings if b.handler == function
            ]

        else:
            parsed_keys = tuple(
                _parse_key(cast(Keys | str, key))
                for key in args
            )

            bindings_to_remove = [
                b for b in self.bindings if b.keys == parsed_keys
            ]

        for binding in bindings_to_remove:
            self.bindings.remove(binding)
            found = True

        if not found:
            raise ValueError(f"Binding not found: {function!r}")

        self._clear_cache()

    add_binding = add
    remove_binding = remove

    def get_bindings_for_keys(self, keys: KeysTuple) -> list[Binding]:
        """
        Return bindings matching exactly `keys`.
        """

        def get() -> list[Binding]:
            result: list[tuple[int, Binding]] = []

            for binding in self.bindings:
                if len(keys) != len(binding.keys):
                    continue

                any_count = 0

                for expected, actual in zip(binding.keys, keys):
                    if expected != actual and expected != Keys.Any:
                        break

                    if expected == Keys.Any:
                        any_count += 1
                else:
                    result.append((any_count, binding))

            # Bindings with fewer `Any` wildcards have higher priority.
            result.sort(key=lambda item: item[0])

            return [item[1] for item in result]

        return self._get_bindings_for_keys_cache.get(keys, get)

    def get_bindings_starting_with_keys(
        self,
        keys: KeysTuple,
    ) -> list[Binding]:
        """
        Return bindings whose sequences start with `keys`.
        """

        def get() -> list[Binding]:
            result: list[Binding] = []

            for binding in self.bindings:
                if len(keys) >= len(binding.keys):
                    continue

                for expected, actual in zip(binding.keys, keys):
                    if expected != actual and expected != Keys.Any:
                        break
                else:
                    result.append(binding)

            return result

        return self._get_bindings_starting_with_keys_cache.get(keys, get)


def _parse_key(key: Keys | str) -> str | Keys:
    """
    Normalize and validate a key definition.
    """
    if isinstance(key, Keys):
        return key

    key = KEY_ALIASES.get(key, key)

    if key == "space":
        key = " "

    try:
        return Keys(key)

    except ValueError:
        if len(key) != 1:
            raise ValueError(f"Invalid key: {key}") from None

    return key


def key_binding(
    filter: FilterOrBool = True,
    eager: FilterOrBool = False,
    is_global: FilterOrBool = False,
    save_before: Callable[[KeyPressEvent], bool] = lambda event: True,
    record_in_macro: FilterOrBool = True,
) -> Callable[[KeyHandlerCallable], Binding]:
    """
    Convert a function into a reusable `Binding` object.
    """
    if save_before is not None and not callable(save_before):
        raise TypeError("save_before must be callable.")

    filter_obj = to_filter(filter)

    def decorator(function: KeyHandlerCallable) -> Binding:
        return Binding(
            (),
            function,
            filter=filter_obj,
            eager=to_filter(eager),
            is_global=to_filter(is_global),
            save_before=save_before,
            record_in_macro=to_filter(record_in_macro),
        )

    return decorator


class _Proxy(KeyBindingsBase):
    """
    Shared proxy base for wrapped key binding collections.
    """

    def __init__(self) -> None:
        self._bindings2: KeyBindingsBase = KeyBindings()
        self._last_version: Hashable = ()

    def _update_cache(self) -> None:
        raise NotImplementedError

    @property
    def bindings(self) -> list[Binding]:
        self._update_cache()
        return self._bindings2.bindings

    @property
    def _version(self) -> Hashable:
        self._update_cache()
        return self._last_version

    def get_bindings_for_keys(self, keys: KeysTuple) -> list[Binding]:
        self._update_cache()
        return self._bindings2.get_bindings_for_keys(keys)

    def get_bindings_starting_with_keys(
        self,
        keys: KeysTuple,
    ) -> list[Binding]:
        self._update_cache()
        return self._bindings2.get_bindings_starting_with_keys(keys)


class ConditionalKeyBindings(_Proxy):
    """
    Conditionally enable/disable all bindings from another registry.
    """

    def __init__(
        self,
        key_bindings: KeyBindingsBase,
        filter: FilterOrBool = True,
    ) -> None:
        super().__init__()

        self.key_bindings = key_bindings
        self.filter = to_filter(filter)

    def _update_cache(self) -> None:
        expected_version = self.key_bindings._version

        if self._last_version == expected_version:
            return

        bindings2 = KeyBindings()

        bindings2.bindings.extend(
            Binding(
                keys=b.keys,
                handler=b.handler,
                filter=self.filter & b.filter,
                eager=b.eager,
                is_global=b.is_global,
                save_before=b.save_before,
                record_in_macro=b.record_in_macro,
            )
            for b in self.key_bindings.bindings
        )

        self._bindings2 = bindings2
        self._last_version = expected_version


class _MergedKeyBindings(_Proxy):
    """
    Merge multiple `KeyBindings` collections into one.
    """

    def __init__(self, registries: Sequence[KeyBindingsBase]) -> None:
        super().__init__()

        self.registries = registries

    def _update_cache(self) -> None:
        expected_version = tuple(
            registry._version
            for registry in self.registries
        )

        if self._last_version == expected_version:
            return

        bindings2 = KeyBindings()

        for registry in self.registries:
            bindings2.bindings.extend(registry.bindings)

        self._bindings2 = bindings2
        self._last_version = expected_version


def merge_key_bindings(
    bindings: Sequence[KeyBindingsBase],
) -> _MergedKeyBindings:
    """
    Merge multiple `KeyBindings` objects together.
    """
    return _MergedKeyBindings(bindings)


class DynamicKeyBindings(_Proxy):
    """
    Dynamically resolve a `KeyBindings` instance at runtime.
    """

    def __init__(
        self,
        get_key_bindings: Callable[[], KeyBindingsBase | None],
    ) -> None:
        self.get_key_bindings = get_key_bindings

        self._dummy = KeyBindings()

    def _update_cache(self) -> None:
        key_bindings = self.get_key_bindings() or self._dummy

        if not isinstance(key_bindings, KeyBindingsBase):
            raise TypeError(
                "get_key_bindings() must return KeyBindingsBase."
            )

        self._bindings2 = key_bindings
        self._last_version = (
            id(key_bindings),
            key_bindings._version,
        )


class GlobalOnlyKeyBindings(_Proxy):
    """
    Wrapper exposing only global bindings.
    """

    def __init__(self, key_bindings: KeyBindingsBase) -> None:
        super().__init__()

        self.key_bindings = key_bindings

    def _update_cache(self) -> None:
        expected_version = self.key_bindings._version

        if self._last_version == expected_version:
            return

        bindings2 = KeyBindings()

        bindings2.bindings.extend(
            binding
            for binding in self.key_bindings.bindings
            if binding.is_global()
        )

        self._bindings2 = bindings2
        self._last_version = expected_version
