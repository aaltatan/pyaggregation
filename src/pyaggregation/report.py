"""Reports: several folds run together over one iterable, in one pass.

```python
report = total(salary, name="payroll") & count(name="managers", where=is_manager)
report(employees)                        # {"payroll": ..., "managers": 2}
report.group_by(department)(employees)   # {"Sales": {...}, "IT": {...}}
```

The input is iterated exactly once, so generators and database cursors work and
only the accumulators are held in memory.
"""

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

from pyvocabulary import validate_name

from .exceptions import (
    DuplicateResultNameError,
    InvalidAggregateError,
    InvalidGroupKeyError,
    InvalidResultNameError,
)

type Value[T] = Callable[[T], Any]
type Condition[T] = Callable[[T], Any]


def identity[V](value: V, /) -> V:
    """Return `value` unchanged: the default `of` of an aggregate."""
    return value


@dataclass(frozen=True, slots=True)
class Fold[V, A, R]:
    """Three pure functions that reduce values to one result.

    `initial` is a function, not a value, so every run starts from a fresh
    accumulator, even a mutable one.

    Example:
    ```python
    >>> longest = Fold(lambda: "", lambda acc, word: max(acc, word, key=len), str.upper)
    >>> aggregate(longest, name="longest")(["fold", "report", "sum"])
    {'longest': 'REPORT'}

    ```

    """

    initial: Callable[[], A]
    step: Callable[[A, V], A]
    finish: Callable[[A], R]


@dataclass(frozen=True, slots=True)
class Aggregate[T]:
    """One named result: `fold` over `of(item)` for every item that passes `where`."""

    name: str
    fold: Fold[Any, Any, Any]
    of: Value[T] = identity
    where: Condition[T] | None = None

    def __post_init__(self) -> None:
        validate_name(self.name, error=InvalidResultNameError)

        # The annotation is a promise to type checkers; callers may still pass anything.
        if not isinstance(cast("object", self.fold), Fold):
            msg = f"Aggregate '{self.name}' must have a Fold, received {self.fold!r}"
            raise InvalidAggregateError(msg)

        check_callable(self.of, role="of", name=self.name)

        if self.where is not None:
            check_callable(self.where, role="where", name=self.name)


@dataclass(frozen=True, slots=True)
class Report[T]:
    """Aggregates in result order. Calling it folds an iterable into one dict.

    Build reports with the built-ins (`total`, `count`, ...) or `aggregate`, then
    join them with `&`. A repeated result name is rejected when the report is built.

    Example:
    ```python
    >>> from pyaggregation import count, total
    >>> report = total(len, name="letters") & count(name="words", where=str.istitle)
    >>> report
    Report(letters, words)
    >>> report(iter(["Fold", "every", "Word"]))
    {'letters': 13, 'words': 2}
    >>> report.group_by(len)(["Fold", "every", "Word"])
    {4: {'letters': 8, 'words': 2}, 5: {'letters': 5, 'words': 0}}

    ```

    """

    aggregates: tuple[Aggregate[T], ...]

    def __post_init__(self) -> None:
        if not self.aggregates:
            msg = "A report needs at least one aggregate, received none"
            raise InvalidAggregateError(msg)

        names = [aggregate.name for aggregate in self.aggregates]

        if duplicate := next((name for name in names if names.count(name) > 1), None):
            raise DuplicateResultNameError(duplicate, dict.fromkeys(names))

    def __call__(self, items: Iterable[T], /) -> dict[str, Any]:
        accumulators = _start(self.aggregates)

        for item in items:
            _step(self.aggregates, accumulators, item)

        return _finish(self.aggregates, accumulators)

    def __and__(self, other: "Report[T]", /) -> "Report[T]":
        match other:
            case Report(aggregates=aggregates):
                return Report((*self.aggregates, *aggregates))
            case _:
                return NotImplemented

    def group_by[K: Hashable](self, key: Callable[[T], K], /) -> "GroupedReport[T, K]":
        """Return a report that folds each group of items with the same `key` separately."""
        return GroupedReport(self, key)

    def __repr__(self) -> str:
        return f"Report({', '.join(aggregate.name for aggregate in self.aggregates)})"


@dataclass(frozen=True, slots=True)
class GroupedReport[T, K: Hashable]:
    """A report per key, still in one pass. Groups come in first-seen order."""

    report: Report[T]
    key: Callable[[T], K]

    def __post_init__(self) -> None:
        if not callable(self.key):
            msg = f"The group_by key must be callable, received {self.key!r}"
            raise InvalidGroupKeyError(msg)

    def __call__(self, items: Iterable[T], /) -> dict[K, dict[str, Any]]:
        aggregates = self.report.aggregates
        groups: dict[K, list[Any]] = {}

        for item in items:
            key = self.key(item)

            if (accumulators := groups.get(key)) is None:
                accumulators = groups[key] = _start(aggregates)

            _step(aggregates, accumulators, item)

        return {key: _finish(aggregates, accumulators) for key, accumulators in groups.items()}

    def __repr__(self) -> str:
        return f"{self.report!r}.group_by({getattr(self.key, '__name__', self.key)})"


def aggregate[T](
    fold: Fold[Any, Any, Any],
    /,
    *,
    name: str,
    of: Value[T] | None = None,
    where: Condition[T] | None = None,
) -> Report[T]:
    """Return a one-result report from any fold: the way to add folds beyond the built-ins.

    Args:
        fold: Reduces the values to the result.
        name: The result's key in the report's dict.
        of: Computes the value folded for each item. Defaults to the item itself.
        where: Keeps only the items it is true for. Runs before `of`.

    Example:
    ```python
    >>> distinct = Fold(frozenset, lambda seen, value: seen | {value}, len)
    >>> aggregate(distinct, name="letters", of=str.lower)("AbBa")
    {'letters': 2}

    ```

    """
    return Report((Aggregate(name, fold, identity if of is None else of, where),))


def check_callable(value: object, /, *, role: str, name: str) -> None:
    """Raise `InvalidAggregateError` unless `value` is callable."""
    if not callable(value):
        msg = f"The {role} of aggregate '{name}' must be callable, received {value!r}"
        raise InvalidAggregateError(msg)


# --- one pass


def _start[T](aggregates: tuple[Aggregate[T], ...]) -> list[Any]:
    return [_named(aggregate, aggregate.fold.initial) for aggregate in aggregates]


def _step[T](aggregates: tuple[Aggregate[T], ...], accumulators: list[Any], item: T) -> None:
    for index, aggregate in enumerate(aggregates):
        try:
            if aggregate.where is None or aggregate.where(item):
                accumulators[index] = aggregate.fold.step(accumulators[index], aggregate.of(item))
        except Exception as error:
            error.add_note(f"in aggregate '{aggregate.name}'")
            raise


def _finish[T](aggregates: tuple[Aggregate[T], ...], accumulators: list[Any]) -> dict[str, Any]:
    return {
        aggregate.name: _named(aggregate, partial(aggregate.fold.finish, accumulator))
        for aggregate, accumulator in zip(aggregates, accumulators, strict=True)
    }


def _named[R](aggregate: Aggregate[Any], call: Callable[[], R]) -> R:
    try:
        return call()
    except Exception as error:
        error.add_note(f"in aggregate '{aggregate.name}'")
        raise
