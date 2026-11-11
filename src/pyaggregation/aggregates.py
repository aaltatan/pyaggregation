"""The built-in aggregates: `total`, `count`, `average`, `share`, `minimum`, `maximum`.

Each returns a one-result `Report`, so they join with `&`. Values pass through
unchanged, so `Decimal` stays `Decimal`; nothing is ever rounded. Averages,
shares, minimum and maximum of no items are `None`, never an exception.
"""

import operator
from collections.abc import Callable
from typing import Any

from .report import Condition, Fold, Report, Value, aggregate, check_callable, identity


def total[T](
    of: Value[T],
    /,
    *,
    name: str,
    where: Condition[T] | None = None,
    start: Any = 0,
) -> Report[T]:
    """Sum the values. Pass `start=Decimal(0)` so an empty money total is a `Decimal`.

    Example:
    ```python
    >>> from decimal import Decimal
    >>> total(Decimal, name="paid", start=Decimal(0))(["1.10", "2.20"])
    {'paid': Decimal('3.30')}

    ```

    """
    return aggregate(Fold(lambda: start, operator.add, identity), name=name, of=of, where=where)


def count[T](*, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Count the items that pass `where` (all of them without it).

    Example:
    ```python
    >>> count(name="evens", where=lambda n: n % 2 == 0)(range(10))
    {'evens': 5}

    ```

    """
    return aggregate(Fold(int, lambda n, _: n + 1, identity), name=name, where=where)


def average[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Average the values: `Decimal` stays `Decimal`, `int` gives `float`, no values give `None`.

    Example:
    ```python
    >>> average(len, name="mean")(["ab", "abcd"]), average(len, name="mean")([])
    ({'mean': 3.0}, {'mean': None})

    ```

    """
    fold = Fold(lambda: (0, 0), _add_counted, _divide)

    return aggregate(fold, name=name, of=of, where=where)


def share[T](*, name: str, where: Condition[T], of: Value[T] | None = None) -> Report[T]:
    """Return the part of the items (or of the total of `of`) for which `where` is true.

    Unlike the other aggregates, `where` does not filter: it splits the items
    into the part and the whole. An empty or zero whole gives `None`.

    Example:
    ```python
    >>> share(name="evens", where=lambda n: n % 2 == 0)([1, 2, 3, 4])
    {'evens': 0.5}
    >>> share(name="big", where=lambda n: n > 2, of=identity)([1, 2, 3, 4])
    {'big': 0.7}

    ```

    """
    check_callable(where, role="where", name=name)

    value: Value[T] = _one if of is None else of

    def step(acc: tuple[Any, Any], item: T) -> tuple[Any, Any]:
        part, whole = acc
        amount = value(item)

        return (part + amount if where(item) else part, whole + amount)

    return aggregate(Fold(lambda: (0, 0), step, _divide), name=name)


def minimum[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the smallest value, or `None` without values.

    Example:
    ```python
    >>> minimum(len, name="shortest")(["fold", "a", "sum"])
    {'shortest': 1}

    ```

    """
    return aggregate(Fold(lambda: None, _keep(min), identity), name=name, of=of, where=where)


def maximum[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the largest value, or `None` without values.

    Example:
    ```python
    >>> maximum(len, name="longest")(["fold", "a", "sum"])
    {'longest': 4}

    ```

    """
    return aggregate(Fold(lambda: None, _keep(max), identity), name=name, of=of, where=where)


# --- folds


def _add_counted(acc: tuple[Any, int], value: Any) -> tuple[Any, int]:
    return (acc[0] + value, acc[1] + 1)


def _one(_: object, /) -> int:
    return 1


def _divide(acc: tuple[Any, Any]) -> Any:
    part, whole = acc

    return None if whole == 0 else part / whole


def _keep(choose: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
    return lambda acc, value: value if acc is None else choose(acc, value)
