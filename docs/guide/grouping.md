# Grouping

`report.group_by(key)` returns a new `GroupedReport` that folds each key separately, still
in one pass. The original report is unchanged.

```python
from pyaggregation import GroupedReport, count, median, total

payroll = (
    total(salary, name="payroll", start=Decimal(0))
    & count(name="headcount")
    & median(salary, name="median_salary")
)

by_department = payroll.group_by(department)

assert isinstance(by_department, GroupedReport)
assert repr(by_department) == "Report(payroll, headcount, median_salary).group_by(department)"

assert by_department(employees) == {
    "Sales": {
        "payroll": Decimal("5500.25"),
        "headcount": 2,
        "median_salary": Decimal("2750.125"),
    },
    "IT": {
        "payroll": Decimal("13500.50"),
        "headcount": 3,
        "median_salary": Decimal("4500.50"),
    },
}
```

Groups come back in the order their first item appeared.

## Several fields

Group by several fields with a key that returns a tuple:

```python
assert count(name="people").group_by(lambda e: (e.department, e.manager))(employees) == {
    ("Sales", True): {"people": 1},
    ("IT", False): {"people": 2},
    ("Sales", False): {"people": 1},
    ("IT", True): {"people": 1},
}
```

The key's results must be hashable. Any callable works: a function, a lambda,
`operator.attrgetter("department")`.

## Empty input

A group exists only once an item has that key, so empty input has no groups:

```python
assert by_department([]) == {}
```

Use an ungrouped report when every key must appear, or fill the missing keys yourself:

```python
expected = ["HR", "IT", "Sales"]
results = by_department(employees)
empty = payroll([])

filled = {key: results.get(key, empty) for key in expected}

assert filled["HR"] == {"payroll": Decimal("0"), "headcount": 0, "median_salary": None}
```

## Errors

A key that is not callable is rejected when the grouped report is built:

```python
from pyaggregation import InvalidGroupKeyError

try:
    payroll.group_by("department")
except InvalidGroupKeyError as error:
    assert str(error) == "The group_by key must be callable, received 'department'"
```

`where` still filters inside each group; filtered-out items still create their group, with
empty results for that aggregate.
