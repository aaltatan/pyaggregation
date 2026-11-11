"""The built-in aggregates. Each returns a one-result `Report`, so they join with `&`.

- Sums: `total`, `product`, `count`, `count_distinct`.
- Averages and spread: `average`, `share`, `variance`, `stdev`.
- Order: `minimum`, `maximum`, `median`, `percentile`, `mode`, `first`, `last`.
- Truth: `some`, `every`.
- Collections: `collect`, `join`.

Values pass through unchanged, so `Decimal` stays `Decimal`; nothing is ever
rounded. Sums and collections of nothing are their empty value (`0`, `1`, `[]`,
`""`); every other aggregate of nothing is `None`, never an exception. `None`
values are not skipped: filter them out with `where`.

Most aggregates keep only a running value. `count_distinct` and `mode` keep one
entry per distinct value; `median`, `percentile`, `collect` and `join` keep
every value until the input ends.
"""

import math
import operator
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from functools import partial
from typing import Any, cast

from .exceptions import InvalidAggregateError
from .report import Condition, Fold, Report, Value, aggregate, check_callable, identity

# Marks "no value yet", so a real `None` value is never mistaken for an empty input.
_MISSING: Any = object()


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


def product[T](
    of: Value[T],
    /,
    *,
    name: str,
    where: Condition[T] | None = None,
    start: Any = 1,
) -> Report[T]:
    """Multiply the values, e.g. growth factors. No values give `start`.

    Example:
    ```python
    >>> product(float, name="growth")([1.5, 2])
    {'growth': 3.0}

    ```

    """
    return aggregate(Fold(lambda: start, operator.mul, identity), name=name, of=of, where=where)


def count[T](*, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Count the items that pass `where` (all of them without it).

    Example:
    ```python
    >>> count(name="evens", where=lambda n: n % 2 == 0)(range(10))
    {'evens': 5}

    ```

    """
    return aggregate(Fold(int, lambda n, _: n + 1, identity), name=name, where=where)


def count_distinct[T](
    of: Value[T], /, *, name: str, where: Condition[T] | None = None
) -> Report[T]:
    """Count the different values. Values must be hashable; `1`, `1.0` and `True` are one value.

    Example:
    ```python
    >>> count_distinct(str.lower, name="letters")("AbBa")
    {'letters': 2}

    ```

    """
    return aggregate(Fold(set, _add_to_set, len), name=name, of=of, where=where)


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


def variance[T](
    of: Value[T],
    /,
    *,
    name: str,
    where: Condition[T] | None = None,
    sample: bool = True,
) -> Report[T]:
    """Return the variance, like `statistics.variance` (or `pvariance` with `sample=False`).

    Computed in one pass with Welford's method, which stays accurate for values
    with a large common offset. A sample needs two values, a population one;
    fewer give `None`. `Decimal` stays `Decimal`.

    Example:
    ```python
    >>> variance(int, name="var")([1, 2, 3]), variance(int, name="var", sample=False)([1, 2, 3])
    ({'var': 1.0}, {'var': 0.666...})

    ```

    """
    _check_type(sample, bool, role="sample", name=name)

    fold = Fold(lambda: (0, 0, 0), _welford, partial(_variance, sample=sample))

    return aggregate(fold, name=name, of=of, where=where)


def stdev[T](
    of: Value[T],
    /,
    *,
    name: str,
    where: Condition[T] | None = None,
    sample: bool = True,
) -> Report[T]:
    """Return the standard deviation: the square root of `variance`, with the same rules.

    Example:
    ```python
    >>> stdev(int, name="sd", sample=False)([2, 4, 4, 4, 5, 5, 7, 9])
    {'sd': 2.0}

    ```

    """
    _check_type(sample, bool, role="sample", name=name)

    fold = Fold(lambda: (0, 0, 0), _welford, partial(_stdev, sample=sample))

    return aggregate(fold, name=name, of=of, where=where)


def minimum[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the smallest value, or `None` without values.

    Example:
    ```python
    >>> minimum(len, name="shortest")(["fold", "a", "sum"])
    {'shortest': 1}

    ```

    """
    return aggregate(Fold(_missing, _keep(min), _present), name=name, of=of, where=where)


def maximum[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the largest value, or `None` without values.

    Example:
    ```python
    >>> maximum(len, name="longest")(["fold", "a", "sum"])
    {'longest': 4}

    ```

    """
    return aggregate(Fold(_missing, _keep(max), _present), name=name, of=of, where=where)


def median[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the middle value, or the mean of the middle two. No values give `None`.

    Example:
    ```python
    >>> median(int, name="m")([3, 1, 2]), median(int, name="m")([4, 1, 3, 2])
    ({'m': 2}, {'m': 2.5})

    ```

    """
    fold = Fold(list, _append, partial(_percentile, at=0.5))

    return aggregate(fold, name=name, of=of, where=where)


def percentile[T](
    of: Value[T],
    /,
    *,
    name: str,
    at: float | Decimal,
    where: Condition[T] | None = None,
) -> Report[T]:
    """Return the value at fraction `at` (0 to 1) of the sorted values, interpolated linearly.

    The same method as SQL's `PERCENTILE_CONT` and NumPy's default: `at=0` is the
    minimum, `at=1` the maximum, `at=0.5` the median. `Decimal` values stay
    `Decimal`, even with a float `at`. No values give `None`.

    Example:
    ```python
    >>> percentile(int, name="p90", at=0.9)(range(1, 11))
    {'p90': 9.1}

    ```

    """
    # The annotation is a promise to type checkers; JSON may still send anything.
    value = cast("object", at)

    if (
        isinstance(value, bool)
        or not isinstance(value, int | float | Decimal)
        or not 0 <= value <= 1
    ):
        msg = f"The at of aggregate '{name}' must be a number from 0 to 1, received {at!r}"
        raise InvalidAggregateError(msg)

    fold = Fold(list, _append, partial(_percentile, at=at))

    return aggregate(fold, name=name, of=of, where=where)


def mode[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the most common value; a tie goes to the value seen first. No values give `None`.

    Example:
    ```python
    >>> mode(str.lower, name="letter")("abBA")
    {'letter': 'a'}

    ```

    """
    return aggregate(Fold(Counter, _add_to_counter, _most_common), name=name, of=of, where=where)


def first[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the first value in input order, or `None` without values.

    Example:
    ```python
    >>> first(str.upper, name="initial", where=str.isalpha)("1ab")
    {'initial': 'A'}

    ```

    """
    return aggregate(Fold(_missing, _keep_first, _present), name=name, of=of, where=where)


def last[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the last value in input order, or `None` without values.

    Example:
    ```python
    >>> last(str.upper, name="final", where=str.isalpha)("ab1")
    {'final': 'B'}

    ```

    """
    return aggregate(Fold(_missing, _keep_last, _present), name=name, of=of, where=where)


def some[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return whether any value is truthy, or `None` without values.

    Example:
    ```python
    >>> some(lambda n: n > 2, name="big")([1, 3]), some(bool, name="big")([])
    ({'big': True}, {'big': None})

    ```

    """
    return aggregate(Fold(lambda: None, _any, identity), name=name, of=of, where=where)


def every[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return whether all values are truthy, or `None` without values.

    No values give `None`, not `True`, like SQL's `EVERY`: "nothing to check"
    must never read as "everything passed".

    Example:
    ```python
    >>> every(lambda n: n > 0, name="positive")([1, 3]), every(bool, name="ok")([])
    ({'positive': True}, {'ok': None})

    ```

    """
    return aggregate(Fold(lambda: None, _all, identity), name=name, of=of, where=where)


def collect[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    """Return the values as a list, in input order. No values give `[]`.

    Example:
    ```python
    >>> collect(str.upper, name="letters", where=str.isalpha)("a1b")
    {'letters': ['A', 'B']}

    ```

    """
    return aggregate(Fold(list, _append, identity), name=name, of=of, where=where)


def join[T](
    of: Value[T],
    /,
    *,
    name: str,
    where: Condition[T] | None = None,
    separator: str = ", ",
) -> Report[T]:
    """Join string values with `separator`, in input order. No values give `""`.

    Example:
    ```python
    >>> join(str.upper, name="codes", separator="-")(["ab", "cd"])
    {'codes': 'AB-CD'}

    ```

    """
    _check_type(separator, str, role="separator", name=name)

    return aggregate(Fold(list, _append, separator.join), name=name, of=of, where=where)


# --- folds
# Accumulators that grow (lists, sets, counters) are mutated in place: `initial`
# makes a fresh one per run, and copying on every step would make a run quadratic.


def _add_counted(acc: tuple[Any, int], value: Any) -> tuple[Any, int]:
    return (acc[0] + value, acc[1] + 1)


def _one(_: object, /) -> int:
    return 1


def _divide(acc: tuple[Any, Any]) -> Any:
    part, whole = acc

    return None if whole == 0 else part / whole


def _missing() -> Any:
    return _MISSING


def _present(acc: Any) -> Any:
    return None if acc is _MISSING else acc


def _keep(choose: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
    return lambda acc, value: value if acc is _MISSING else choose(acc, value)


def _keep_first(acc: Any, value: Any) -> Any:
    return value if acc is _MISSING else acc


def _keep_last(_: Any, value: Any) -> Any:
    return value


def _any(acc: Any, value: Any) -> bool:
    return bool(acc) or bool(value)


def _all(acc: Any, value: Any) -> bool:
    return acc is not False and bool(value)


def _append(acc: list[Any], value: Any) -> list[Any]:
    acc.append(value)

    return acc


def _add_to_set(acc: set[Any], value: Any) -> set[Any]:
    acc.add(value)

    return acc


def _add_to_counter(acc: Counter[Any], value: Any) -> Counter[Any]:
    acc[value] += 1

    return acc


def _most_common(acc: Counter[Any]) -> Any:
    # `max` returns the first of equal counts, and a Counter keeps first-seen order.
    return max(acc, key=acc.__getitem__) if acc else None


def _welford(acc: tuple[int, Any, Any], value: Any) -> tuple[int, Any, Any]:
    count, mean, squares = acc
    count += 1
    delta = value - mean
    mean += delta / count

    return (count, mean, squares + delta * (value - mean))


def _variance(acc: tuple[int, Any, Any], *, sample: bool) -> Any:
    count, _, squares = acc
    degrees = count - 1 if sample else count

    return squares / degrees if degrees > 0 else None


def _stdev(acc: tuple[int, Any, Any], *, sample: bool) -> Any:
    if (result := _variance(acc, sample=sample)) is None:
        return None

    return result.sqrt() if isinstance(result, Decimal) else math.sqrt(result)


def _percentile(acc: list[Any], *, at: float | Decimal) -> Any:
    if not acc:
        return None

    values = sorted(acc)

    # `Decimal * float` raises; a float `at` like 0.9 is meant as the decimal 0.9.
    if isinstance(at, float) and isinstance(values[0], Decimal):
        at = Decimal(str(at))

    position = at * (len(values) - 1)
    index = min(math.floor(position), len(values) - 1)
    weight = position - index

    if weight == 0:
        return values[index]

    return values[index] + (values[index + 1] - values[index]) * weight


def _check_type(value: object, kind: type, /, *, role: str, name: str) -> None:
    if not isinstance(value, kind):
        msg = f"The {role} of aggregate '{name}' must be a {kind.__name__}, received {value!r}"
        raise InvalidAggregateError(msg)
