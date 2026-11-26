# API

`T` is the type of the items a report reads. Every name below is importable from
`pyaggregation`.

## Reports

### `Report[T]`

```py
@dataclass(frozen=True, slots=True)
class Report[T]:
    aggregates: tuple[Aggregate[T], ...]
```

Aggregates in result order. Usually built with the built-ins or `aggregate` and `&`, not
directly.

| Member | Description |
| --- | --- |
| `report(items: Iterable[T]) -> dict[str, Any]` | read `items` once, return one result per aggregate |
| `a & b -> Report[T]` | a new report with the aggregates of `a` then `b` |
| `report.group_by(key: Callable[[T], K]) -> GroupedReport[T, K]` | the same report per key |
| `repr(report)` | `Report(payroll, headcount)` |

Raises when built: `InvalidAggregateError` (no aggregates), `DuplicateResultNameError`.

Guide: [Reports and &](../guide/reports.md).

### `GroupedReport[T, K: Hashable]`

```py
@dataclass(frozen=True, slots=True)
class GroupedReport[T, K: Hashable]:
    report: Report[T]
    key: Callable[[T], K]
```

| Member | Description |
| --- | --- |
| `grouped(items: Iterable[T]) -> dict[K, dict[str, Any]]` | one result dict per key, in first-seen order |
| `repr(grouped)` | `Report(payroll).group_by(department)` |

Raises when built: `InvalidGroupKeyError` if `key` is not callable.

Guide: [Grouping](../guide/grouping.md).

### `Aggregate[T]`

```py
@dataclass(frozen=True, slots=True)
class Aggregate[T]:
    name: str
    fold: Fold[Any, Any, Any]
    of: Value[T] = identity
    where: Condition[T] | None = None
```

One named result: `fold` over `of(item)` for every item that passes `where`. Raises when
built: `InvalidResultNameError`, `InvalidAggregateError` (not a `Fold`, `of` or `where` not
callable).

### `Fold[V, A, R]`

```py
@dataclass(frozen=True, slots=True)
class Fold[V, A, R]:
    initial: Callable[[], A]
    step: Callable[[A, V], A]
    finish: Callable[[A], R]
```

Three functions that reduce values to one result. `initial` runs once per run (and per
group), so the accumulator may be mutable.

Guide: [Your own aggregates](../guide/custom.md).

### `aggregate`

```py
aggregate(
    fold: Fold[Any, Any, Any],
    /,
    *,
    name: str,
    of: Value[T] | None = None,
    where: Condition[T] | None = None,
) -> Report[T]
```

A one-result report from any fold. `of` defaults to `identity`; `where` runs before `of`.

### `identity`

```py
identity(value: V, /) -> V
```

Returns `value` unchanged: the default `of`.

### `Value[T]`, `Condition[T]`

```py
type Value[T] = Callable[[T], Any]
type Condition[T] = Callable[[T], Any]
```

The types of `of` and `where`. A condition's result is used for its truth value.

## Built-in aggregates

Every built-in returns a one-result `Report[T]`. `name` is required and keyword-only;
`where: Condition[T] | None = None` is optional on all of them.

| Signature | Result | No values give |
| --- | --- | --- |
| `total(of, /, *, name, where=None, start=0)` | `start` plus every value | `start` |
| `product(of, /, *, name, where=None, start=1)` | `start` times every value | `start` |
| `count(*, name, where=None)` | number of items passing `where` | `0` |
| `count_distinct(of, /, *, name, where=None)` | number of distinct (hashable) values | `0` |
| `average(of, /, *, name, where=None)` | mean | `None` |
| `share(*, name, where, of=None)` | part where `where` is true, over the whole; of items, or of `of`'s total | `None` (also for a zero whole) |
| `variance(of, /, *, name, where=None, sample=True)` | sample or population variance | `None` (fewer than 2 values for a sample) |
| `stdev(of, /, *, name, where=None, sample=True)` | square root of `variance` | `None` |
| `minimum(of, /, *, name, where=None)` | smallest value | `None` |
| `maximum(of, /, *, name, where=None)` | largest value | `None` |
| `median(of, /, *, name, where=None)` | middle value, or mean of the middle two | `None` |
| `percentile(of, /, *, name, at, where=None)` | linear interpolation at `at` (0 to 1) | `None` |
| `mode(of, /, *, name, where=None)` | most common value, first seen on ties | `None` |
| `first(of, /, *, name, where=None)` | first value | `None` |
| `last(of, /, *, name, where=None)` | last value | `None` |
| `some(of, /, *, name, where=None)` | whether any value is truthy | `None` |
| `every(of, /, *, name, where=None)` | whether all values are truthy | `None` |
| `collect(of, /, *, name, where=None)` | list of values | `[]` |
| `join(of, /, *, name, where=None, separator=", ")` | string values joined | `""` |

Raise when built: `InvalidResultNameError`, and `InvalidAggregateError` for a non-callable
`of` or `where`, an `at` that is not a number from 0 to 1, a non-`bool` `sample` or a
non-`str` `separator`.

Guide: [Built-in aggregates](../guide/builtins.md).

## JSON

### `ReportCompiler[T]`

```py
ReportCompiler(
    values: Compiler[Value[T]],
    conditions: Compiler[Condition[T]],
    keys: Compiler[Callable[[T], Hashable]] | None = None,
    /,
    *,
    start: Any = 0,
)
```

| Member | Description |
| --- | --- |
| `compile(definition: ReportDict \| Mapping[str, Any], /) -> Report[T] \| GroupedReport[T, Hashable]` | build a report; a `GroupedReport` when `group_by` is present |

`start` is passed to every `total`. Raises `InvalidReportDefinitionError` for a wrong shape;
errors from the injected compilers and from building aggregates keep their type and get an
`at $...` note.

Guide: [Compiling reports from JSON](../guide/compiling.md).

### `Compiler[F]`

```py
class Compiler[F](Protocol):
    def compile(self, definition: Any, /) -> F: ...
```

Anything with a `compile` method, such as pyformula's `FormulaCompiler` or
pyspecification's `PredicateCompiler`.

### `ReportDict`, `AggregateDict`

```py
class AggregateDict(TypedDict):
    name: str
    fold: str
    of: NotRequired[Any]
    where: NotRequired[Any]


class ReportDict(TypedDict):
    aggregates: list[AggregateDict]
    group_by: NotRequired[Any]
```

Type hints for definitions. Fold options (`at`, `sample`, `separator`) are accepted too; see
[Report format](format.md).

### `get_report_json_schema`

```py
get_report_json_schema(
    value_schema: Mapping[str, Any],
    condition_schema: Mapping[str, Any],
    key_schema: Mapping[str, Any] | None = None,
    /,
) -> dict[str, Any]
```

The JSON Schema (2020-12) of the definitions `ReportCompiler.compile` accepts. Without
`key_schema`, `group_by` is not allowed.

Guide: [JSON Schema](../guide/json-schema.md).

### `VALUE_SCHEMA_ID`, `CONDITION_SCHEMA_ID`, `KEY_SCHEMA_ID`

```py
VALUE_SCHEMA_ID = "urn:pyaggregation:value"
CONDITION_SCHEMA_ID = "urn:pyaggregation:condition"
KEY_SCHEMA_ID = "urn:pyaggregation:key"
```

The `$id`s under which the three sub-schemas are embedded (in `$defs` as `value`,
`condition` and `key`).

## Exceptions

`PyaggregationError`, `InvalidResultNameError`, `DuplicateResultNameError`,
`InvalidAggregateError`, `InvalidGroupKeyError`, `InvalidReportDefinitionError`: see
[Exceptions](exceptions.md).
