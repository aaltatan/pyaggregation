# Report format

The JSON accepted by `ReportCompiler.compile` and described by `get_report_json_schema`.

## Report

```json
{
  "aggregates": [ <aggregate>, ... ],
  "group_by": <key>
}
```

| Key | Required | Value |
| --- | --- | --- |
| `aggregates` | yes | a non-empty list of aggregates; result names must be unique |
| `group_by` | no | a key definition, compiled by the `keys` compiler; rejected when the compiler has none |

No other keys are allowed.

## Aggregate

```json
{"name": "payroll", "fold": "total", "of": <value>, "where": <condition>}
```

| Key | Value |
| --- | --- |
| `name` | the result's key: an ASCII identifier, `^[a-zA-Z_][a-zA-Z0-9_]*$` |
| `fold` | one of the folds below |
| `of` | a value definition, compiled by the `values` compiler |
| `where` | a condition definition, compiled by the `conditions` compiler |
| `at`, `sample`, `separator` | plain JSON options of some folds |

## Folds

Which keys each fold requires or allows, besides `name` and `fold`. Any other key is an
error.

| `fold` | Required | Optional |
| --- | --- | --- |
| `total` | `of` | `where` |
| `product` | `of` | `where` |
| `count` | | `where` |
| `count_distinct` | `of` | `where` |
| `average` | `of` | `where` |
| `share` | `where` | `of` |
| `variance` | `of` | `where`, `sample` (boolean) |
| `stdev` | `of` | `where`, `sample` (boolean) |
| `minimum` | `of` | `where` |
| `maximum` | `of` | `where` |
| `median` | `of` | `where` |
| `percentile` | `of`, `at` (number, 0 to 1) | `where` |
| `mode` | `of` | `where` |
| `first` | `of` | `where` |
| `last` | `of` | `where` |
| `some` | `of` | `where` |
| `every` | `of` | `where` |
| `collect` | `of` | `where` |
| `join` | `of` | `where`, `separator` (string) |

`total` always gets the compiler's `start`. `product` starts at `1`.

These rules are the compiler's own, checked against the source here:

```python
from pyaggregation.compilers import FOLDS

assert FOLDS["count"].required == frozenset()
assert FOLDS["share"].required == {"where"} and FOLDS["share"].optional == {"of"}
assert FOLDS["percentile"].required == {"of", "at"}
assert FOLDS["join"].optional == {"where", "separator"}
assert FOLDS["stdev"].optional == FOLDS["variance"].optional == {"where", "sample"}
assert len(FOLDS) == 19
```

## A complete example

```json
{
  "aggregates": [
    {"name": "payroll", "fold": "total", "of": "pay"},
    {"name": "managers", "fold": "count", "where": "is_manager"},
    {"name": "manager_share", "fold": "share", "where": "is_manager", "of": "pay"},
    {"name": "spread", "fold": "stdev", "of": "pay", "sample": false},
    {"name": "p90", "fold": "percentile", "of": "pay", "at": 0.9},
    {"name": "team", "fold": "join", "of": "name", "separator": " / "}
  ],
  "group_by": "department"
}
```

## Error paths

Errors carry a JSON path from `$`: in the message for `InvalidReportDefinitionError`, and as
an `at $...` exception note for everything else.

| Problem | Path |
| --- | --- |
| report is not an object, misses `aggregates` or has unknown keys | `$` |
| `aggregates` is not a non-empty list | `$.aggregates` |
| a duplicate result name | `$.aggregates` |
| an aggregate is not an object, misses a key or has a forbidden one | `$.aggregates[i]` |
| unknown `fold` | `$.aggregates[i].fold` |
| invalid `name` | `$.aggregates[i].name` |
| the values / conditions compiler fails | `$.aggregates[i].of` / `$.aggregates[i].where` |
| bad `at`, `sample` or `separator` | `$.aggregates[i]` |
| no key compiler, or the keys compiler fails | `$.group_by` |
