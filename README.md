# pyaggregation

Summaries over collections, computed in one pass. Composable with `&`, groupable by any key,
and definable as JSON.

```python
report = (
    total(salary, name="payroll", start=Decimal(0))
    & average(salary, name="average_salary")
    & count(name="managers", where=is_manager)
    & median(salary, name="median_salary")
)

report(employees)
# {'payroll': Decimal('19000.75'), 'average_salary': Decimal('3800.15'), 'managers': 2, ...}

report.group_by(department)(employees)
# {'Sales': {...}, 'IT': {...}}
```

A `Report` runs several aggregates together over **any iterable**: a list, a generator, a
database cursor. Each item is read exactly once, so a report over a million rows needs one
loop, not one loop per number.

| Piece | What it does |
| --- | --- |
| [Built-ins](#built-in-aggregates) | 19 aggregates: `total`, `count`, `average`, `median`, `percentile`, `stdev`, `mode`, `join`, ... |
| [`Report`](#composing-with-) | Aggregates joined with `&`; calling it returns one dict |
| [`group_by`](#grouping) | The same report per key, still in one pass |
| [`Fold` and `aggregate`](#your-own-aggregates) | Your own aggregate from three small functions |
| [`ReportCompiler`](#from-json) | Builds a report from JSON; errors carry a JSON path |
| [`get_report_json_schema`](#json-schema) | The JSON Schema of that JSON, for editors and API validation |

**When to use it.** Dashboards, KPI tiles, exports and API endpoints that summarise records,
especially when users choose the numbers (a report builder) or the input is too large to loop
over once per metric. **When not to.** If the data sits in a database and the summary is
fixed, a SQL `GROUP BY` is faster. For one number from a list, `sum()` is fine.

## Installation

```bash
uv add pyaggregation
```

or, with pip:

```bash
pip install pyaggregation
```

It needs Python 3.12 or newer. The only runtime dependency is
[pyvocabulary](https://github.com/aaltatan/pyvocabulary). For JSON definitions,
[pyformula](https://github.com/aaltatan/pyformula) (values) and
[pyspecification](https://github.com/aaltatan/pyspecification) (conditions) fit the
compiler, but they are optional: any object with a `compile()` method works.

## Quick start

The examples below build on each other and are run by the test suite. A comment directly
under a line shows what that line outputs or raises.

```python
from dataclasses import dataclass
from decimal import Decimal

from pyaggregation import average, count, maximum, median, minimum, total


@dataclass(frozen=True)
class Employee:
    name: str
    department: str
    salary: Decimal
    manager: bool = False


employees = [
    Employee("Alice", "Sales", Decimal("3000.00"), manager=True),
    Employee("Bob", "IT", Decimal("4500.50")),
    Employee("Carol", "Sales", Decimal("2500.25")),
    Employee("Dan", "IT", Decimal("5000.00"), manager=True),
    Employee("Eve", "IT", Decimal("4000.00")),
]


def salary(employee: Employee) -> Decimal:
    return employee.salary


def department(employee: Employee) -> str:
    return employee.department


def is_manager(employee: Employee) -> bool:
    return employee.manager


payroll = (
    total(salary, name="payroll", start=Decimal(0))
    & count(name="headcount")
    & count(name="managers", where=is_manager)
    & average(salary, name="average_salary")
    & median(salary, name="median_salary")
    & minimum(salary, name="lowest")
    & maximum(salary, name="highest")
)

payroll
# Report(payroll, headcount, managers, average_salary, median_salary, lowest, highest)

payroll(employees)
# {'payroll': Decimal('19000.75'), 'headcount': 5, 'managers': 2, 'average_salary':
# Decimal('3800.15'), 'median_salary': Decimal('4000.00'), 'lowest': Decimal('2500.25'),
# 'highest': Decimal('5000.00')}
```

Every aggregate takes a `name` (its key in the result) and most take:

- `of`: what to aggregate for each item. Any callable: a function, a lambda,
  `operator.attrgetter("salary")`, or a pyformula `Formula`.
- `where`: which items to include. Any callable returning something truthy, such as a
  pyspecification `Predicate`. It runs before `of`, so `of` never sees an item it
  would fail on.

## Composing with `&`

`&` joins reports into a new one; the originals are unchanged. Results come back in the
order you joined them.

```python
from pyaggregation import share

headline = total(salary, name="payroll", start=Decimal(0)) & count(name="headcount")

with_shares = headline & share(name="manager_share", where=is_manager)

headline(employees)
# {'payroll': Decimal('19000.75'), 'headcount': 5}

with_shares(employees)
# {'payroll': Decimal('19000.75'), 'headcount': 5, 'manager_share': 0.4}
```

A name used twice is rejected when the report is built, not when the first row arrives:

```python
headline & count(name="payroll")
# DuplicateResultNameError: Result name 'payroll' is used more than once. Result names: payroll,
# headcount
```

So is a name that cannot be a JSON key or Python identifier:

```python
count(name="head count")
# InvalidResultNameError: Invalid result name: 'head count', you should follow the python
# variable naming convention: name must start with a letter and can only contain letters,
# numbers and underscores
```

## Filtering with `where`

`where` filters each aggregate separately, so one pass can compare groups side by side:

```python
by_role = (
    average(salary, name="manager_average", where=is_manager)
    & average(salary, name="staff_average", where=lambda e: not e.manager)
    & count(name="well_paid", where=lambda e: e.salary >= 4000)
)

by_role(employees)
# {'manager_average': Decimal('4000.00'), 'staff_average':
# Decimal('3666.916666666666666666666667'), 'well_paid': 3}
```

`share` is the one aggregate where `where` does not filter: it splits items into a part and a
whole. Without `of` it is a share of items; with `of` it is a share of a total.

```python
shares = share(name="of_people", where=is_manager) & share(
    name="of_payroll", where=is_manager, of=salary
)

shares(employees)
# {'of_people': 0.4, 'of_payroll': Decimal('0.4210360117363788271515598068')}
```

## Grouping

`group_by(key)` returns a new report that folds each key separately, still in one pass.
Groups come back in the order their first item appeared.

```python
by_department = payroll.group_by(department)

by_department
# Report(payroll, headcount, managers, average_salary, median_salary, lowest,
# highest).group_by(department)

by_department(employees)["IT"]
# {'payroll': Decimal('13500.50'), 'headcount': 3, 'managers': 1, 'average_salary':
# Decimal('4500.166666666666666666666667'), 'median_salary': Decimal('4500.50'), 'lowest':
# Decimal('4000.00'), 'highest': Decimal('5000.00')}

list(by_department(employees))
# ['Sales', 'IT']
```

Group by several fields with a key that returns a tuple:

```python
count(name="people").group_by(lambda e: (e.department, e.manager))(employees)
# {('Sales', True): {'people': 1}, ('IT', False): {'people': 2}, ('Sales', False): {'people':
# 1}, ('IT', True): {'people': 1}}
```

Empty input has no groups, because a group exists only once an item has that key:

```python
by_department([])
# {}
```

## Built-in aggregates

| Aggregate | Result | No values give | Memory |
| --- | --- | --- | --- |
| `total(of, start=0)` | sum of values | `start` | constant |
| `product(of, start=1)` | product of values | `start` | constant |
| `count()` | number of items that pass `where` | `0` | constant |
| `count_distinct(of)` | number of different values | `0` | one entry per distinct value |
| `average(of)` | mean | `None` | constant |
| `share(where, of=None)` | part of the items, or of the total of `of` | `None` | constant |
| `variance(of, sample=True)` | sample (or population) variance | `None` | constant |
| `stdev(of, sample=True)` | sample (or population) standard deviation | `None` | constant |
| `minimum(of)` / `maximum(of)` | smallest / largest value | `None` | constant |
| `median(of)` | middle value, or mean of the middle two | `None` | every value |
| `percentile(of, at=0.9)` | value at a fraction of the sorted values | `None` | every value |
| `mode(of)` | most common value, first seen on ties | `None` | one entry per distinct value |
| `first(of)` / `last(of)` | first / last value in input order | `None` | constant |
| `some(of)` / `every(of)` | whether any / all values are truthy | `None` | constant |
| `collect(of)` | list of values in input order | `[]` | every value |
| `join(of, separator=", ")` | string values joined | `""` | every value |

All of them also take `name` (required) and `where` (optional).

### Statistics

`variance` and `stdev` match Python's `statistics` module: `sample=True` (the default) is
`statistics.variance`, `sample=False` is `statistics.pvariance`. They use Welford's
one-pass method, which stays accurate even when values share a large offset.

```python
from pyaggregation import percentile, stdev, variance

spread = (
    stdev(salary, name="sample_stdev")
    & stdev(salary, name="population_stdev", sample=False)
    & percentile(salary, name="p25", at=0.25)
    & percentile(salary, name="p90", at=0.9)
)

spread(employees)
# {'sample_stdev': Decimal('1036.828119796140559902272581'), 'population_stdev':
# Decimal('927.3672627389862741638917628'), 'p25': Decimal('3000.00'), 'p90':
# Decimal('4800.200')}

variance(float, name="var")([1e9 + 4, 1e9 + 7, 1e9 + 13, 1e9 + 16])
# {'var': 30.0}
```

`percentile` interpolates linearly between the two nearest values, like SQL's
`PERCENTILE_CONT` and NumPy's default. `at=0` is the minimum, `at=1` the maximum and
`at=0.5` the median. `at` is checked when the report is built:

```python
percentile(salary, name="p", at=90)
# InvalidAggregateError: The at of aggregate 'p' must be a number from 0 to 1, received 90
```

### Order, truth and collections

```python
from pyaggregation import collect, count_distinct, every, first, join, last, mode, some

people = (
    first(lambda e: e.name, name="first_hired")
    & last(lambda e: e.name, name="last_hired")
    & count_distinct(department, name="departments")
    & mode(department, name="largest_department")
    & some(is_manager, name="has_managers")
    & every(lambda e: e.salary > 2000, name="all_above_2000")
    & collect(lambda e: e.name, name="managers", where=is_manager)
    & join(lambda e: e.name, name="team", separator=" / ")
)

people(employees)
# {'first_hired': 'Alice', 'last_hired': 'Eve', 'departments': 2, 'largest_department': 'IT',
# 'has_managers': True, 'all_above_2000': True, 'managers': ['Alice', 'Dan'], 'team': 'Alice /
# Bob / Carol / Dan / Eve'}
```

`every` of nothing is `None`, not `True`, so "nothing to check" never reads as "everything
passed":

```python
every(is_manager, name="all_managers")([])
# {'all_managers': None}
```

## Money and `Decimal`

Values pass through unchanged, so `Decimal` stays `Decimal` and nothing is ever rounded:

```python
average(salary, name="average")(employees)
# {'average': Decimal('3800.15')}

percentile(salary, name="p90", at=0.9)(employees)
# {'p90': Decimal('4800.200')}
```

A float `at` such as `0.9` with `Decimal` values is read as the decimal `0.9`, so the
percentile stays exact.

Pass `start=Decimal(0)` to `total` so that an empty total is `Decimal('0')` and not the
integer `0`:

```python
total(salary, name="payroll")([])
# {'payroll': 0}

total(salary, name="payroll", start=Decimal(0))([])
# {'payroll': Decimal('0')}
```

Mixing `Decimal` with `float` raises instead of quietly losing precision:

```python
total(lambda e: float(e.salary), name="payroll", start=Decimal(0))(employees)
# TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'
```

Rounding is your job, once, at the end:

```python
average(salary, name="average")(employees)["average"].quantize(Decimal("0.01"))
# Decimal('3800.15')
```

## Edge cases

**Empty or fully filtered input.** A report always returns every key. Sums and collections
give their empty value; everything else gives `None`, never an exception or `NaN`:

```python
from pyaggregation import product

everything = (
    total(salary, name="total", start=Decimal(0))
    & product(salary, name="product")
    & count(name="count")
    & average(salary, name="average")
    & median(salary, name="median")
    & stdev(salary, name="stdev")
    & collect(salary, name="collect")
    & join(lambda e: e.name, name="join")
)

everything([])
# {'total': Decimal('0'), 'product': 1, 'count': 0, 'average': None, 'median': None, 'stdev':
# None, 'collect': [], 'join': ''}

everything(employees[:1])["stdev"] is None
# True
```

A sample standard deviation needs two values, so one employee gives `None`.

**`None` values are not skipped.** Unlike SQL's `NULL`, a `None` is a value. Arithmetic on
it fails, with a note naming the aggregate:

```python
bonuses = [Decimal("100"), None, Decimal("250")]

try:
    total(lambda bonus: bonus, name="bonuses")(bonuses)
except TypeError as error:
    print(error, error.__notes__)
# unsupported operand type(s) for +: 'decimal.Decimal' and 'NoneType' ["in aggregate 'bonuses'"]
```

Skip them explicitly with `where`:

```python
total(lambda bonus: bonus, name="bonuses", where=lambda bonus: bonus is not None)(bonuses)
# {'bonuses': Decimal('350')}

first(lambda bonus: bonus, name="first_missing", where=lambda bonus: bonus is None)(bonuses)
# {'first_missing': None}
```

**Errors keep their type.** Whatever `of`, `where` or a fold raises comes through
unchanged, with only an `in aggregate '...'` note added, so your `except` clauses still work.

**Generators are read once.** A report reads its input exactly once, so a generator or
cursor works, and a spent one gives an empty report:

```python
def rows():
    yield from employees  # a database cursor works the same way


stream = rows()

count(name="headcount")(stream)
# {'headcount': 5}

count(name="headcount")(stream)
# {'headcount': 0}
```

**Equal values.** `count_distinct` follows Python equality, so `1`, `1.0`, `Decimal(1)` and
`True` are one value. `mode` gives ties to the value seen first:

```python
count_distinct(lambda value: value, name="distinct")([1, 1.0, Decimal(1), True, 2])
# {'distinct': 2}

mode(lambda value: value, name="mode")(["b", "a", "a", "b"])
# {'mode': 'b'}
```

## Your own aggregates

A `Fold` is three plain functions: `initial()` makes the starting value, `step(acc, value)`
adds one value, `finish(acc)` turns the result into the answer. `aggregate` names it and adds
`of` and `where`, and the result joins with `&` like any built-in.

```python
from pyaggregation import Fold, aggregate

salary_range = Fold(
    initial=lambda: None,
    step=lambda acc, value: (
        (value, value) if acc is None else (min(acc[0], value), max(acc[1], value))
    ),
    finish=lambda acc: None if acc is None else acc[1] - acc[0],
)

with_range = payroll & aggregate(salary_range, name="salary_range", of=salary)

with_range(employees)["salary_range"]
# Decimal('2499.75')

with_range.group_by(department)(employees)["Sales"]["salary_range"]
# Decimal('499.75')
```

`initial` is a function, not a value, so a fold may start from a list or a set: every run
gets a fresh one.

## From JSON

A report can be stored or sent as JSON, for example from a report builder in your UI.
`aggregates` is a list, so a duplicate name is an error and not silently dropped:

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

`ReportCompiler` does not know what is inside `of`, `where` and `group_by`; it hands them to
compilers you pass in. Anything with a `compile(definition)` method works. Here pyformula
compiles the values (so `of` can be arithmetic), and a tiny lookup compiles conditions and
keys:

```python
import json

from pyformula import FormulaCompiler, variable

from pyaggregation import ReportCompiler


@variable()
def pay(employee: Employee) -> Decimal:
    return employee.salary


class Named:
    """The smallest compiler: a JSON string names a Python callable."""

    def __init__(self, **entries):
        self.entries = entries

    def compile(self, definition):
        return self.entries[definition]


compiler = ReportCompiler(
    FormulaCompiler[Employee]({"pay": pay, "name": lambda e: e.name}),
    Named(is_manager=is_manager),
    Named(department=department),
    start=Decimal(0),
)

definition = json.loads(
    """
    {
      "aggregates": [
        {"name": "payroll", "fold": "total", "of": "pay"},
        {"name": "yearly", "fold": "total",
         "of": {"operator": "multiply", "expressions": ["pay", 12]}},
        {"name": "managers", "fold": "count", "where": "is_manager"},
        {"name": "p90", "fold": "percentile", "of": "pay", "at": 0.9}
      ],
      "group_by": "department"
    }
    """,
    parse_float=Decimal,
)

report = compiler.compile(definition)

report
# Report(payroll, yearly, managers, p90).group_by(department)

report(employees)["IT"]
# {'payroll': Decimal('13500.50'), 'yearly': Decimal('162006.00'), 'managers': 1, 'p90':
# Decimal('4900.100')}
```

- `start` is set once on the compiler, because JSON has no `Decimal`. Use
  `parse_float=Decimal` too, so numbers inside the JSON (such as `at`) stay exact.
- Without a third (keys) compiler, a definition with `group_by` is rejected, so an API can
  offer ungrouped reports only.
- For conditions, pyspecification's `PredicateCompiler` fits the same slot and lets users
  write `{"name": "salary__ge", "args": [4000]}`-style rules.

### Errors point at the JSON

Every problem is found when compiling, before any item is read. Shape errors say where:

```python
compiler.compile({"aggregates": [{"name": "p", "fold": "percentile", "of": "pay"}]})
# InvalidReportDefinitionError: Invalid report at $.aggregates[0]: missing 'at'

compiler.compile({"aggregates": [{"name": "n", "fold": "count", "of": "pay"}]})
# InvalidReportDefinitionError: Invalid report at $.aggregates[0]: unknown 'of'. Allowed keys:
# fold, name, where

compiler.compile({"aggregates": [{"name": "n", "fold": "average_of"}]})
# InvalidReportDefinitionError: Invalid report at $.aggregates[0].fold: unknown fold
# 'average_of'. Available folds: average, collect, count, count_distinct, every, first, join,
# last, maximum, median, minimum, mode, percentile, product, share, some, stdev, total, variance
```

Errors from your compilers keep their type and get the path as a note:

```python
try:
    compiler.compile({"aggregates": [{"name": "n", "fold": "count", "where": "is_boss"}]})
except KeyError as error:
    print(repr(error), error.__notes__)
# KeyError('is_boss') ['at $.aggregates[0].where']
```

### JSON Schema

`get_report_json_schema` describes exactly what the compiler accepts, for form builders,
editor autocompletion or request validation. Pass the schemas of your `of`, `where` and
(optionally) `group_by` languages; each is embedded under its own `$id`.

```python
from pyaggregation import get_report_json_schema

schema = get_report_json_schema(
    {"type": "string"},
    {"enum": ["is_manager"]},
    {"enum": ["department"]},
)

schema["$defs"]["percentile"]["required"]
# ['name', 'fold', 'at', 'of']

schema["$defs"]["percentile"]["properties"]["at"]
# {'type': 'number', 'minimum': 0, 'maximum': 1}

schema["properties"]["aggregates"]["minItems"]
# 1
```

Each fold has its own variant, so `of`, `where` and options such as `at` are required or
forbidden exactly as the compiler requires or forbids them.

## Errors

| Exception | Raised when |
| --- | --- |
| `PyaggregationError` | Base class of everything below |
| `InvalidResultNameError` | A `name` is not a Python identifier (also a `ValueError`) |
| `DuplicateResultNameError` | Two aggregates in one report share a name |
| `InvalidAggregateError` | A non-callable `of`/`where`, a bad `at`, `sample` or `separator`, an empty report |
| `InvalidGroupKeyError` | The `group_by` key is not callable |
| `InvalidReportDefinitionError` | A JSON definition has the wrong shape (the message has the path) |

Everything raised while a report *runs* (by your `of`, `where`, key or fold) keeps its own
type and gets an `in aggregate '...'` note.

## Development

```bash
uv sync
```

```bash
uv run pytest --cov --cov-branch
```

```bash
uvx ruff check . && uvx ruff format --check . && uvx pyright src
```

See [`docs/DESIGN.md`](docs/DESIGN.md) for the decisions behind the API and
[`PHASES.md`](PHASES.md) for the plan.

## License

GPL-3.0-only.
