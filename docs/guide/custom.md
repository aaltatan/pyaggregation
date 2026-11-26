# Your own aggregates

## `Fold`: three functions

A `Fold` is three plain functions:

- `initial()` makes the starting accumulator,
- `step(acc, value)` adds one value and returns the new accumulator,
- `finish(acc)` turns the accumulator into the result.

`aggregate(fold, name=..., of=..., where=...)` names it and adds `of` and `where`. The result
is a one-result `Report`, so it joins with `&` and groups like any built-in.

```python
from pyaggregation import Fold, aggregate, count

salary_range = Fold(
    initial=lambda: None,
    step=lambda acc, value: (
        (value, value) if acc is None else (min(acc[0], value), max(acc[1], value))
    ),
    finish=lambda acc: None if acc is None else acc[1] - acc[0],
)

with_range = count(name="headcount") & aggregate(salary_range, name="salary_range", of=salary)

assert with_range(employees) == {"headcount": 5, "salary_range": Decimal("2499.75")}
assert with_range.group_by(department)(employees)["Sales"]["salary_range"] == Decimal("499.75")
assert with_range([]) == {"headcount": 0, "salary_range": None}
```

Without `of`, the value is the item itself (`identity`):

```python
longest = Fold(lambda: "", lambda acc, word: max(acc, word, key=len), str.upper)

assert aggregate(longest, name="longest")(["fold", "report", "sum"]) == {"longest": "REPORT"}
```

## Mutable accumulators

`initial` is a function, not a value, so a fold may start from a list, set or dict: every
run gets a fresh one. Mutating it in `step` is fine (and avoids copying on every item), as
long as `step` returns it:

```python
def add_to(acc: dict[str, Decimal], employee: Employee) -> dict[str, Decimal]:
    acc[employee.name] = employee.salary

    return acc


salaries_by_name = Fold(dict, add_to, lambda acc: dict(sorted(acc.items())))
report = aggregate(salaries_by_name, name="salaries", where=is_manager)

assert report(employees) == {
    "salaries": {"Alice": Decimal("3000.00"), "Dan": Decimal("5000.00")}
}
assert report(employees) == report(employees)  # no state leaks between runs
```

## A reusable factory

Wrap `aggregate` in a function with the same signature style as the built-ins (positional
`of`, keyword-only `name` and `where`) and it reads like one:

```python
from pyaggregation import Condition, Report, Value


def spread[T](of: Value[T], /, *, name: str, where: Condition[T] | None = None) -> Report[T]:
    return aggregate(salary_range, name=name, of=of, where=where)


assert spread(len, name="spread")(["a", "abcd"]) == {"spread": 3}
```

## Validation

`aggregate` checks its arguments when it is called, not when the report runs:

```python
from pyaggregation import InvalidAggregateError

try:
    aggregate(len, name="bad")
except InvalidAggregateError as error:
    assert str(error).startswith("Aggregate 'bad' must have a Fold")

try:
    aggregate(longest, name="bad", of="salary")
except InvalidAggregateError as error:
    assert str(error) == "The of of aggregate 'bad' must be callable, received 'salary'"
```

Custom folds are Python-only: a JSON definition can use only the built-in folds (see
[Compiling reports from JSON](compiling.md)).
