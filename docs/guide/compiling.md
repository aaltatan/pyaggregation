# Compiling reports from JSON

A report can be stored or sent as JSON, for example from a report builder in your UI:

```json
{
  "aggregates": [
    {"name": "payroll", "fold": "total", "of": "pay"},
    {"name": "yearly", "fold": "total", "of": {"operator": "multiply", "expressions": ["pay", 12]}},
    {"name": "managers", "fold": "count", "where": "is_manager"},
    {"name": "p90", "fold": "percentile", "of": "pay", "at": 0.9},
    {"name": "team", "fold": "join", "of": "name", "separator": ", "}
  ],
  "group_by": "department"
}
```

`aggregates` is a list, so a duplicate name is an error and not silently dropped. Every fold
and its fields are listed in the [Report format](../reference/format.md).

## `ReportCompiler`

`ReportCompiler` does not know what is inside `of`, `where` and `group_by`; it hands them to
compilers you pass in. Anything with a `compile(definition)` method works.

```py
ReportCompiler(values, conditions, keys=None, /, *, start=0)
```

- `values` compiles each `of`.
- `conditions` compiles each `where`.
- `keys` compiles `group_by`. Without it, grouped definitions are rejected, so an API can
  offer ungrouped reports only.
- `start` is the `start` of every `total`, since JSON has no `Decimal`.

The smallest compiler maps a JSON string to a Python callable:

```python
from pyaggregation import ReportCompiler


class Named:
    """A JSON string names a Python callable."""

    def __init__(self, **entries):
        self.entries = entries

    def compile(self, definition):
        return self.entries[definition]


compiler = ReportCompiler(
    Named(pay=salary, name=lambda e: e.name),
    Named(is_manager=is_manager),
    Named(department=department),
    start=Decimal(0),
)

report = compiler.compile(
    {
        "aggregates": [
            {"name": "payroll", "fold": "total", "of": "pay"},
            {"name": "managers", "fold": "count", "where": "is_manager"},
            {"name": "team", "fold": "join", "of": "name", "separator": " / "},
        ],
        "group_by": "department",
    }
)

assert repr(report) == "Report(payroll, managers, team).group_by(department)"
assert report(employees)["Sales"] == {
    "payroll": Decimal("5500.25"),
    "managers": 1,
    "team": "Alice / Carol",
}
```

`compile` returns a `Report`, or a `GroupedReport` when the definition has `group_by`.

## With pyformula and pyspecification

pyformula's `FormulaCompiler` fits the `values` slot, so `of` can be arithmetic.
pyspecification's `PredicateCompiler` fits the `conditions` slot, so `where` can be a rule
with arguments. Use `parse_float=Decimal` when reading the JSON so numbers inside it (such
as `at`) stay exact.

```python
import json

from pyformula import FormulaCompiler, variable
from pyspecification import Predicate, PredicateCompiler, object_rule


@variable()
def pay(employee: Employee) -> Decimal:
    return employee.salary


@object_rule()
def department__eq(employee: Employee, name: str) -> bool:
    return employee.department == name


compiler = ReportCompiler(
    FormulaCompiler[Employee]({"pay": pay}),
    PredicateCompiler[Employee, bool](
        {"department__eq": department__eq},
        lambda wrapper: Predicate(lambda _: wrapper["operator"] == "all"),
    ),
    start=Decimal(0),
)

definition = json.loads(
    """
    {
      "aggregates": [
        {"name": "payroll", "fold": "total", "of": "pay"},
        {"name": "yearly", "fold": "total",
         "of": {"operator": "multiply", "expressions": ["pay", 12]}},
        {"name": "it", "fold": "count",
         "where": {"name": "department__eq", "args": ["IT"], "kwargs": {}, "inverse": false}},
        {"name": "p90", "fold": "percentile", "of": "pay", "at": 0.9}
      ]
    }
    """,
    parse_float=Decimal,
)

assert compiler.compile(definition)(employees) == {
    "payroll": Decimal("19000.75"),
    "yearly": Decimal("228009.00"),
    "it": 3,
    "p90": Decimal("4800.200"),
}
```

## Errors point at the JSON

Every problem is found when compiling, before any item is read. Shape errors are
`InvalidReportDefinitionError` and say where:

```python
from pyaggregation import InvalidReportDefinitionError

compiler = ReportCompiler(Named(pay=salary), Named(is_manager=is_manager))


def error_of(definition) -> str:
    try:
        compiler.compile(definition)
    except InvalidReportDefinitionError as error:
        return str(error)

    raise AssertionError


assert error_of({"aggregates": [{"name": "p", "fold": "percentile", "of": "pay"}]}) == (
    "Invalid report at $.aggregates[0]: missing 'at'"
)
assert error_of({"aggregates": [{"name": "n", "fold": "count", "of": "pay"}]}) == (
    "Invalid report at $.aggregates[0]: unknown 'of'. Allowed keys: fold, name, where"
)
assert error_of({"aggregates": []}) == (
    "Invalid report at $.aggregates: expected a non-empty list, received []"
)
assert error_of({"aggregates": [{"name": "n", "fold": "count"}], "group_by": "x"}) == (
    "Invalid report at $.group_by: grouping needs a key compiler, and none was given"
)
assert error_of({"aggregates": [{"name": "n", "fold": "average_of"}]}).startswith(
    "Invalid report at $.aggregates[0].fold: unknown fold 'average_of'. Available folds: "
)
```

Errors from your compilers, and from building the aggregates (`InvalidResultNameError`,
`DuplicateResultNameError`, `InvalidAggregateError`), keep their type and get the JSON path
as a note:

```python
try:
    compiler.compile({"aggregates": [{"name": "n", "fold": "count", "where": "is_boss"}]})
except KeyError as error:
    assert error.__notes__ == ["at $.aggregates[0].where"]

try:
    compiler.compile({"aggregates": [{"name": "p", "fold": "percentile", "of": "pay", "at": 2}]})
except Exception as error:
    assert type(error).__name__ == "InvalidAggregateError"
    assert error.__notes__ == ["at $.aggregates[0]"]
```
