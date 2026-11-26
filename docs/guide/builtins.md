# Built-in aggregates

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
| `percentile(of, at)` | value at a fraction of the sorted values | `None` | every value |
| `mode(of)` | most common value, first seen on ties | `None` | one entry per distinct value |
| `first(of)` / `last(of)` | first / last value in input order | `None` | constant |
| `some(of)` / `every(of)` | whether any / all values are truthy | `None` | constant |
| `collect(of)` | list of values in input order | `[]` | every value |
| `join(of, separator=", ")` | string values joined | `""` | every value |

All of them take `name` (required, keyword-only) and `where` (optional). `of` is the first,
positional argument, except for `count` (no `of`) and `share` (keyword `of`, optional).

## Sums and counts

```python
from pyaggregation import count, count_distinct, product, total

sums = (
    total(salary, name="payroll", start=Decimal(0))
    & count(name="headcount")
    & count_distinct(department, name="departments")
)

assert sums(employees) == {
    "payroll": Decimal("19000.75"),
    "headcount": 5,
    "departments": 2,
}

assert product(float, name="growth")([1.5, 2]) == {"growth": 3.0}
```

`count_distinct` keeps a set, so values must be hashable, and it follows Python equality:
`1`, `1.0`, `Decimal(1)` and `True` are one value.

```python
assert count_distinct(lambda value: value, name="distinct")([1, 1.0, Decimal(1), True, 2]) == {
    "distinct": 2
}
```

## Averages and spread

`variance` and `stdev` match Python's `statistics` module: `sample=True` (the default) is
`statistics.variance`, `sample=False` is `statistics.pvariance`. They use Welford's one-pass
method, which stays accurate even when values share a large offset.

```python
from pyaggregation import average, stdev, variance

spread = (
    average(salary, name="average")
    & stdev(salary, name="sample_stdev")
    & stdev(salary, name="population_stdev", sample=False)
)

assert spread(employees) == {
    "average": Decimal("3800.15"),
    "sample_stdev": Decimal("1036.828119796140559902272581"),
    "population_stdev": Decimal("927.3672627389862741638917628"),
}

assert variance(float, name="var")([1e9 + 4, 1e9 + 7, 1e9 + 13, 1e9 + 16]) == {"var": 30.0}
```

A sample needs two values and a population one; fewer give `None`.

## Order

```python
from pyaggregation import maximum, median, minimum, mode, percentile

order = (
    minimum(salary, name="lowest")
    & maximum(salary, name="highest")
    & median(salary, name="median")
    & percentile(salary, name="p25", at=0.25)
    & percentile(salary, name="p90", at=0.9)
    & mode(department, name="largest_department")
)

assert order(employees) == {
    "lowest": Decimal("2500.25"),
    "highest": Decimal("5000.00"),
    "median": Decimal("4000.00"),
    "p25": Decimal("3000.00"),
    "p90": Decimal("4800.200"),
    "largest_department": "IT",
}
```

`percentile` interpolates linearly between the two nearest values, like SQL's
`PERCENTILE_CONT` and NumPy's default. `at=0` is the minimum, `at=1` the maximum and
`at=0.5` the median. `at` must be a number from 0 to 1, checked when the report is built:

```python
from pyaggregation import InvalidAggregateError

try:
    percentile(salary, name="p", at=90)
except InvalidAggregateError as error:
    assert str(error) == "The at of aggregate 'p' must be a number from 0 to 1, received 90"
```

`mode` gives ties to the value seen first:

```python
assert mode(lambda value: value, name="mode")(["b", "a", "a", "b"]) == {"mode": "b"}
```

## First, last and truth

```python
from pyaggregation import every, first, last, some

facts = (
    first(lambda e: e.name, name="first_hired")
    & last(lambda e: e.name, name="last_hired")
    & some(is_manager, name="has_managers")
    & every(lambda e: e.salary > 2000, name="all_above_2000")
)

assert facts(employees) == {
    "first_hired": "Alice",
    "last_hired": "Eve",
    "has_managers": True,
    "all_above_2000": True,
}
```

`every` of nothing is `None`, not `True`, like SQL's `EVERY`, so "nothing to check" never
reads as "everything passed":

```python
assert every(is_manager, name="all_managers")([]) == {"all_managers": None}
```

## Collections

```python
from pyaggregation import collect, join

names = collect(lambda e: e.name, name="managers", where=is_manager) & join(
    lambda e: e.name, name="team", separator=" / "
)

assert names(employees) == {
    "managers": ["Alice", "Dan"],
    "team": "Alice / Bob / Carol / Dan / Eve",
}
```

`sample` must be a `bool` and `separator` a `str`; anything else raises
`InvalidAggregateError` when the aggregate is built.
