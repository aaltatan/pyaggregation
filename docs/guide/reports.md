# Reports and `&`

A `Report` is a tuple of aggregates in result order. Calling it folds an iterable into one
dict, reading each item exactly once.

## Building a report

Every built-in aggregate returns a one-result report. `&` joins reports into a new one; the
originals are unchanged, and results come back in the order you joined them.

```python
from pyaggregation import Report, count, share, total

headline = total(salary, name="payroll", start=Decimal(0)) & count(name="headcount")
with_shares = headline & share(name="manager_share", where=is_manager)

assert isinstance(headline, Report)
assert repr(with_shares) == "Report(payroll, headcount, manager_share)"

assert headline(employees) == {"payroll": Decimal("19000.75"), "headcount": 5}
assert with_shares(employees) == {
    "payroll": Decimal("19000.75"),
    "headcount": 5,
    "manager_share": 0.4,
}
```

`&` only joins reports. Joining anything else raises `TypeError`:

```python
try:
    headline & 1
except TypeError:
    pass
else:
    raise AssertionError
```

## Result names

`name` is the result's key in the dict. It must be an ASCII Python identifier, so it is
always a valid JSON key and attribute name, and it is checked when the aggregate is built:

```python
from pyaggregation import InvalidResultNameError

try:
    count(name="head count")
except InvalidResultNameError as error:
    assert "head count" in str(error)
```

A name used twice in one report is rejected when the report is built, not when the first
row arrives:

```python
from pyaggregation import DuplicateResultNameError

try:
    headline & count(name="payroll")
except DuplicateResultNameError as error:
    assert str(error) == (
        "Result name 'payroll' is used more than once. Result names: payroll, headcount"
    )
```

## Any iterable, read once

A report reads its input exactly once, so lists, generators and database cursors all work.
Only the accumulators are kept in memory (see the memory column in
[Built-in aggregates](builtins.md)).

```python
def rows():
    yield from employees  # a database cursor works the same way


stream = rows()

assert count(name="headcount")(stream) == {"headcount": 5}
assert count(name="headcount")(stream) == {"headcount": 0}  # the generator is spent
```

## Reports are values

Reports are frozen dataclasses: they can be built once at import time, shared between
threads and reused for any number of calls. Each call starts from fresh accumulators.

```python
assert headline(employees) == headline(employees)
assert headline.aggregates[0].name == "payroll"
```

An empty report is not allowed:

```python
from pyaggregation import InvalidAggregateError

try:
    Report(())
except InvalidAggregateError as error:
    assert str(error) == "A report needs at least one aggregate, received none"
```
