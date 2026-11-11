# pyaggregation design

Usage lives in the README; this file records the decisions and why.

```python
report = (
    total(salary, name="payroll", start=Decimal(0))
    & average(salary, name="average_salary")
    & count(name="managers", where=is_manager())
    & share(name="manager_share", where=is_manager())
)
report(employees)  # {'payroll': Decimal(...), ..., 'manager_share': 0.25}
report.group_by(department)(employees)  # {'Sales': {...}, 'IT': {...}}
```

## Values

- `Fold[V, A, R]` is a frozen dataclass of three pure functions: `initial() -> A`,
  `step(acc, value) -> A`, `finish(acc) -> R`. `initial` is a function, not a value, so a
  custom fold may use a fresh mutable accumulator per run without sharing it between runs.
  A fold knows nothing about items, names or filters; it only folds values.
- `Aggregate[T]` is one named result: `name`, `fold`, `of: Callable[[T], V]` (defaults to
  identity) and `where: Callable[[T], Any] | None`. Keeping `of` and `where` as fields,
  not baked into a closure, lets `repr` show them and keeps every fold reusable.
- `Report[T]` is a frozen dataclass holding `aggregates: tuple[Aggregate[T], ...]`.
  Calling it with any `Iterable[T]` returns `dict[str, Any]` in aggregate order.
- `&` concatenates aggregates and returns a new `Report`. Every built-in returns a one-item
  `Report`, so `total(...) & count(...)` needs no separate "aggregate plus aggregate" case.
- Validation runs in `__post_init__`, so `&`, built-ins and direct construction fail the same
  way, when built: names pass `pyvocabulary.validate_name` (they become dict keys and JSON
  names), `of`/`where` are callable, and a repeated name raises `DuplicateResultNameError`.
- No `|`, `~` or removal operator: nobody asked.

## One pass

The input is iterated exactly once, so generators and database cursors work and nothing is
held in memory but the accumulators:

```text
accs = [a.fold.initial() for a in aggregates]
for item in items:
    for i, a in enumerate(aggregates):
        if a.where is None or a.where(item):
            accs[i] = a.fold.step(accs[i], a.of(item))
return {a.name: a.fold.finish(acc) for a, acc in zip(aggregates, accs)}
```

`where` runs before `of`, so `of` never sees an item it would fail on (e.g. a missing
salary on a filtered-out row). An exception from `of`, `where` or a fold propagates with its
own type and gets a note naming the aggregate (`in aggregate 'payroll'`), never a wrapper.

## Grouping

- `report.group_by(key, /)` returns a `GroupedReport[T, K]`; the report is unchanged.
  Calling it returns `dict[K, dict[str, Any]]` with groups in first-seen order, still in one
  pass (one accumulator list per key). Keys must be hashable.
- Several keys are one key returning a tuple: `group_by(lambda e: (e.department, e.year))`.
  No nested `group_by`, no `&` on a `GroupedReport`: compose first, group last.
- Empty input gives `{}`: a group exists only if an item had that key.
- A separate class, not a `key` field on `Report`, because the return type differs.

## Built-ins

| Built-in | Signature | Result | Empty input |
| --- | --- | --- | --- |
| `total` | `total(of, /, *, name, where=None, start=0)` | `start + sum of values` | `start` |
| `count` | `count(*, name, where=None)` | items that pass `where` | `0` |
| `average` | `average(of, /, *, name, where=None)` | `sum / n` | `None` |
| `share` | `share(*, name, where, of=None)` | part / whole | `None` |
| `minimum` | `minimum(of, /, *, name, where=None)` | smallest value | `None` |
| `maximum` | `maximum(of, /, *, name, where=None)` | largest value | `None` |
| `product` | `product(of, /, *, name, where=None, start=1)` | `start * product of values` | `start` |
| `count_distinct` | `count_distinct(of, /, *, name, where=None)` | number of different values | `0` |
| `variance` | `variance(of, /, *, name, where=None, sample=True)` | Welford, one pass | `None` |
| `stdev` | `stdev(of, /, *, name, where=None, sample=True)` | square root of `variance` | `None` |
| `median` | `median(of, /, *, name, where=None)` | middle value, or mean of the two | `None` |
| `percentile` | `percentile(of, /, *, name, at, where=None)` | linear interpolation at `at` | `None` |
| `mode` | `mode(of, /, *, name, where=None)` | most common value, first on ties | `None` |
| `first` | `first(of, /, *, name, where=None)` | first value in input order | `None` |
| `last` | `last(of, /, *, name, where=None)` | last value in input order | `None` |
| `some` | `some(of, /, *, name, where=None)` | any value truthy | `None` |
| `every` | `every(of, /, *, name, where=None)` | all values truthy | `None` |
| `collect` | `collect(of, /, *, name, where=None)` | list of values | `[]` |
| `join` | `join(of, /, *, name, where=None, separator=", ")` | values joined | `""` |

- `name` is required and keyword-only: result keys are always explicit, never guessed from a
  function or lambda name.
- `share` is the one built-in whose `where` does not filter: it splits items into part and
  whole. Without `of` it is the share of items (`count where / count`); with `of` it is the
  share of a total (managers' share of payroll). `where` is required, since a share of
  everything is always 1. A zero whole gives `None` as well.
- `aggregate(fold, /, *, name, of=None, where=None)` is the public way to add any other fold.
  The built-ins are written with it.
- Memory: most built-ins keep one running value. `count_distinct` and `mode` keep one entry
  per distinct value; `median`, `percentile`, `collect` and `join` keep every value until the
  input ends, so on a huge cursor prefer the constant-memory ones.
- `variance` and `stdev` use Welford's method, not `sum of squares - square of sum`, which
  loses all precision when values share a large offset (timestamps, account numbers). A
  sample needs two values, a population one; fewer give `None`.
- `percentile` is SQL's `PERCENTILE_CONT` (NumPy's default): `at` from 0 to 1, checked when
  built; `bool`, `NaN` and out-of-range values are rejected. `median` is `at=0.5`. A float
  `at` with `Decimal` values is read as the decimal it was written as (`0.9`, not
  `0.90000000000000002`), so the result stays an exact `Decimal`.
- `some` and `every` give `None` on no values, like SQL: `every` of nothing must not read as
  "everything passed".
- `mode` keeps first-seen order on ties (like `statistics.mode`); `count_distinct` follows
  Python equality, so `1`, `1.0`, `Decimal(1)` and `True` are one value.
- Growing accumulators (lists, sets, counters) are mutated in place. `initial` gives each run
  a fresh one, and copying on every step would make a run quadratic.
- Not included, by choice: argmin/argmax (return items, not values), `having`-style filters
  on groups, sorting groups (pyordering).

## Empty input and `Decimal`

- Sums and collections of nothing are their empty value (`total` and `product` give
  `start`, `count` and `count_distinct` give `0`, `collect` gives `[]`, `join` gives `""`).
  Every other aggregate of nothing is `None`, never an exception or `NaN`. A report on an
  empty or fully filtered input always returns a full dict.
- `None` values are not skipped (unlike SQL's `NULL`): `total` and `minimum` of a `None`
  raise `TypeError` with an `in aggregate` note, while `first`, `last`, `mode` and
  `count_distinct` treat `None` as a value. Filter with `where` to skip them.
- Money stays `Decimal`: values pass through unchanged, `Decimal + Decimal` stays exact, and
  `Decimal + float` raises `TypeError` instead of silently losing precision.
- `total` needs `start=Decimal(0)` only so an empty total is `Decimal(0)` and not `0`.
  `average` and `share` do not: they start at `0` and `0 + Decimal` is `Decimal`.
- Averages and shares of `Decimal` divide under the current `decimal` context. Rounding is
  the caller's job (`quantize`); the package never rounds.
- Averages and shares of `int` return `float` (true division).

## JSON

A definition is an object; `aggregates` is a list (not a mapping keyed by name, because JSON
parsers silently keep the last of two equal keys, and a duplicate must be an error):

```json
{
  "aggregates": [
    {"name": "payroll", "fold": "total", "of": "salary"},
    {"name": "managers", "fold": "count", "where": {"is_manager": {}}},
    {"name": "manager_share", "fold": "share", "where": {"is_manager": {}}}
  ],
  "group_by": "department"
}
```

- `ReportCompiler(values, conditions, keys=None, /, *, start=0)` delegates, like pyruleset:
  `of` to a values compiler (pyformula's `FormulaCompiler`), `where` to a conditions compiler
  (pyspecification's `PredicateCompiler`), `group_by` to an optional keys compiler. Without
  one, `group_by` is rejected, so an API can offer ungrouped reports only.
- `start` is set once per compiler (`start=Decimal(0)` in a money app), not per definition,
  because JSON has no `Decimal`.
- `fold` names a built-in. `of` is required for every fold but `count` (where it is
  rejected) and `share` (where it is optional); `where` is required for `share`. Literal
  options sit next to them: `at` (required for `percentile`), `sample` (`variance`, `stdev`)
  and `separator` (`join`); any other fold rejects them. Bad option values raise
  `InvalidAggregateError` with an `at $.aggregates[i]` note. A registry of custom folds for
  JSON waits until a project needs one; Python's `aggregate` covers them.
- The compiler returns a `Report`, or a `GroupedReport` when `group_by` is present.
- Shape errors raise `InvalidReportDefinitionError` with the path in the message. Errors from
  the injected compilers keep their type and get a note via `pyvocabulary.located`
  (`at $.aggregates[1].where`). An empty `aggregates` list is rejected: a report with no
  results is a mistake.

## Schema

`get_report_json_schema(value_schema, condition_schema, key_schema=None)`: an object with
`aggregates` (`minItems: 1`), each item a `oneOf` per fold that requires and forbids `of` and
`where` as above, embedding the injected schemas under their own `$id`. `group_by` appears
only when `key_schema` is given.

## Errors

`PyaggregationError` is the base. `InvalidResultNameError` (also a `ValueError`),
`DuplicateResultNameError`, `InvalidAggregateError` (a non-callable `of`/`where`, a missing
`where` on `share`, a report with no aggregates) and `InvalidGroupKeyError` (a non-callable
`group_by` key) are raised when a report is built; `InvalidReportDefinitionError` by the
compiler. Messages say what is wrong and what is valid: "Result name 'payroll' is used more
than once. Result names: payroll, managers".

## Later

SQL compilation (`SUM`, `COUNT(*) FILTER (WHERE ...)`, `GROUP BY`) is a separate compiler
that works from the JSON definition, since Python callables cannot become SQL. Each built-in
fold maps to one SQL aggregate; the empty-input rules above match SQL except that `SUM` of no
rows is `NULL`, which that compiler will `COALESCE` to `start`.
