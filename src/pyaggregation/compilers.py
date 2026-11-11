"""Compile a report from JSON: `{"aggregates": [{"name", "fold", "of", "where"}], "group_by"}`.

pyaggregation does not know the expression languages inside `of`, `where` and
`group_by`. They are delegated to injected compilers, e.g. pyformula's
`FormulaCompiler` for values and pyspecification's `PredicateCompiler` for conditions.
"""

from collections.abc import Callable, Hashable, Mapping
from typing import Any, NamedTuple, NotRequired, Protocol, TypedDict, cast

from pyvocabulary import index_path, key_path, located, validate_name

from .aggregates import (
    average,
    collect,
    count,
    count_distinct,
    every,
    first,
    join,
    last,
    maximum,
    median,
    minimum,
    mode,
    percentile,
    product,
    share,
    some,
    stdev,
    total,
    variance,
)
from .exceptions import (
    DuplicateResultNameError,
    InvalidAggregateError,
    InvalidReportDefinitionError,
    InvalidResultNameError,
)
from .report import Condition, GroupedReport, Report, Value

type Build = Callable[[str, Any, Any, dict[str, Any]], Report[Any]]


class FoldSpec(NamedTuple):
    """The JSON fields of one fold, besides `name` and `fold`, and how to build it."""

    required: frozenset[str]
    optional: frozenset[str]
    build: Build


def _of_first(build: Callable[..., Report[Any]]) -> Build:
    return lambda name, of, where, options: build(of, name=name, where=where, **options)


_OF = frozenset({"of"})
_WHERE = frozenset({"where"})


def _simple(build: Callable[..., Report[Any]]) -> FoldSpec:
    return FoldSpec(_OF, _WHERE, _of_first(build))


def _count(name: str, _of: Any, where: Any, _options: dict[str, Any]) -> Report[Any]:
    return count(name=name, where=where)


def _share(name: str, of: Any, where: Any, _options: dict[str, Any]) -> Report[Any]:
    return share(name=name, where=where, of=of)


FOLDS: Mapping[str, FoldSpec] = {
    "average": _simple(average),
    "collect": _simple(collect),
    "count": FoldSpec(frozenset(), _WHERE, _count),
    "count_distinct": _simple(count_distinct),
    "every": _simple(every),
    "first": _simple(first),
    "join": FoldSpec(_OF, _WHERE | {"separator"}, _of_first(join)),
    "last": _simple(last),
    "maximum": _simple(maximum),
    "median": _simple(median),
    "minimum": _simple(minimum),
    "mode": _simple(mode),
    "percentile": FoldSpec(_OF | {"at"}, _WHERE, _of_first(percentile)),
    "product": _simple(product),
    "share": FoldSpec(_WHERE, _OF, _share),
    "some": _simple(some),
    "stdev": FoldSpec(_OF, _WHERE | {"sample"}, _of_first(stdev)),
    "total": _simple(total),
    "variance": FoldSpec(_OF, _WHERE | {"sample"}, _of_first(variance)),
}

# Plain JSON values passed to a built-in as they are; `of` and `where` are compiled.
_OPTIONS = frozenset({"at", "sample", "separator"})

_REPORT_KEYS = frozenset({"aggregates", "group_by"})


class AggregateDict(TypedDict):
    name: str
    fold: str
    of: NotRequired[Any]
    where: NotRequired[Any]


class ReportDict(TypedDict):
    aggregates: list[AggregateDict]
    group_by: NotRequired[Any]


class Compiler[F](Protocol):
    """Anything with a `compile(definition) -> F` method."""

    def compile(self, definition: Any, /) -> F: ...


class ReportCompiler[T]:
    """Compile report definitions, delegating `of`, `where` and `group_by` to injected compilers.

    Every problem is reported here, before any item is folded. Errors from the
    injected compilers keep their type and get a note with the full JSON path.

    Args:
        values: Compiles each `of`.
        conditions: Compiles each `where`.
        keys: Compiles `group_by`. Without it, grouped definitions are rejected.
        start: The `start` of every `total`, e.g. `Decimal(0)` in a money app,
            since JSON has no `Decimal`.

    Example:
    ```python
    >>> class Field:
    ...     def compile(self, name):
    ...         return lambda item: item[name]
    >>> compiler = ReportCompiler(Field(), Field(), Field())
    >>> report = compiler.compile({
    ...     "aggregates": [
    ...         {"name": "stock", "fold": "total", "of": "quantity"},
    ...         {"name": "on_sale", "fold": "count", "where": "sale"},
    ...     ],
    ...     "group_by": "shop",
    ... })
    >>> report
    Report(stock, on_sale).group_by(<lambda>)
    >>> report([
    ...     {"shop": "north", "quantity": 3, "sale": True},
    ...     {"shop": "north", "quantity": 4, "sale": False},
    ... ])
    {'north': {'stock': 7, 'on_sale': 1}}

    ```

    """

    __slots__ = ("_conditions", "_keys", "_start", "_values")

    def __init__(
        self,
        values: Compiler[Value[T]],
        conditions: Compiler[Condition[T]],
        keys: Compiler[Callable[[T], Hashable]] | None = None,
        /,
        *,
        start: Any = 0,
    ) -> None:
        self._values = values
        self._conditions = conditions
        self._keys = keys
        self._start = start

    def compile(
        self, definition: ReportDict | Mapping[str, Any], /
    ) -> Report[T] | GroupedReport[T, Hashable]:
        """Compile `definition` into a `Report`, or a `GroupedReport` with `group_by`.

        Raises:
            InvalidReportDefinitionError: If the definition has the wrong shape.

        """
        _check_keys(definition, required={"aggregates"}, allowed=_REPORT_KEYS, path="$")

        path = key_path("$", "aggregates")
        items = definition["aggregates"]

        if not isinstance(items, list) or not items:
            msg = f"Invalid report at {path}: expected a non-empty list, received {items!r}"
            raise InvalidReportDefinitionError(msg)

        compiled = [
            self._compile_aggregate(item, index_path(path, index))
            for index, item in enumerate(cast("list[Any]", items))
        ]

        with located(path, DuplicateResultNameError):
            report = Report(tuple(aggregate for each in compiled for aggregate in each.aggregates))

        if "group_by" not in definition:
            return report

        path = key_path("$", "group_by")

        if self._keys is None:
            msg = f"Invalid report at {path}: grouping needs a key compiler, and none was given"
            raise InvalidReportDefinitionError(msg)

        with located(path, Exception):
            key = self._keys.compile(definition["group_by"])

        return report.group_by(key)

    def _compile_aggregate(self, item: Any, path: str) -> Report[T]:
        _check_keys(item, required=set(), allowed=None, path=path)

        fold = item.get("fold")

        if fold not in FOLDS:
            msg = (
                f"Invalid report at {key_path(path, 'fold')}: unknown fold {fold!r}. "
                f"Available folds: {', '.join(FOLDS)}"
            )
            raise InvalidReportDefinitionError(msg)

        required, optional, build = FOLDS[fold]
        _check_keys(
            item,
            required={"name", "fold", *required},
            allowed={"name", "fold", *required, *optional},
            path=path,
        )

        with located(key_path(path, "name"), InvalidResultNameError):
            name = validate_name(item["name"], error=InvalidResultNameError)

        of = where = None

        if "of" in item:
            with located(key_path(path, "of"), Exception):
                of = self._values.compile(item["of"])

        if "where" in item:
            with located(key_path(path, "where"), Exception):
                where = self._conditions.compile(item["where"])

        options = {key: item[key] for key in _OPTIONS & item.keys()}

        if fold == "total":
            options["start"] = self._start

        with located(path, InvalidAggregateError):
            return build(name, of, where, options)


def _check_keys(
    item: Any, *, required: set[str], allowed: set[str] | frozenset[str] | None, path: str
) -> None:
    if not isinstance(item, Mapping):
        msg = f"Invalid report at {path}: expected an object, received {item!r}"
        raise InvalidReportDefinitionError(msg)

    keys = set(cast("Mapping[str, Any]", item))

    if missing := sorted(required - keys):
        msg = f"Invalid report at {path}: missing {', '.join(map(repr, missing))}"
        raise InvalidReportDefinitionError(msg)

    if allowed is not None and (unknown := sorted(keys - allowed)):
        msg = (
            f"Invalid report at {path}: unknown {', '.join(map(repr, unknown))}. "
            f"Allowed keys: {', '.join(sorted(allowed))}"
        )
        raise InvalidReportDefinitionError(msg)
