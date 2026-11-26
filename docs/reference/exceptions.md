# Exceptions

```text
Exception
└── PyaggregationError
    ├── InvalidResultNameError          (also pyvocabulary's InvalidNameError, a ValueError)
    ├── DuplicateResultNameError        (also a ValueError)
    ├── InvalidAggregateError           (also a TypeError)
    ├── InvalidGroupKeyError            (also a TypeError)
    └── InvalidReportDefinitionError    (also a ValueError)
```

Every exception raised by pyaggregation itself derives from `PyaggregationError`, so one
`except` clause catches them all:

```python
from pyaggregation import (
    DuplicateResultNameError,
    InvalidAggregateError,
    InvalidGroupKeyError,
    InvalidReportDefinitionError,
    InvalidResultNameError,
    PyaggregationError,
)

for error_type in (
    DuplicateResultNameError,
    InvalidAggregateError,
    InvalidGroupKeyError,
    InvalidReportDefinitionError,
    InvalidResultNameError,
):
    assert issubclass(error_type, PyaggregationError)

assert issubclass(InvalidResultNameError, ValueError)
assert issubclass(DuplicateResultNameError, ValueError)
assert issubclass(InvalidReportDefinitionError, ValueError)
assert issubclass(InvalidAggregateError, TypeError)
assert issubclass(InvalidGroupKeyError, TypeError)
```

## When each one is raised

All of them are raised while a report is **built** or **compiled**, never while it runs.

| Exception | Raised by | Example message |
| --- | --- | --- |
| `InvalidResultNameError` | a `name` that is not an ASCII Python identifier | `Invalid result name: 'head count', ...` |
| `DuplicateResultNameError` | two aggregates in one report with the same name | `Result name 'payroll' is used more than once. Result names: payroll, headcount` |
| `InvalidAggregateError` | a non-callable `of`/`where`, a non-`Fold` fold, a bad `at`, `sample` or `separator`, an empty report | `The at of aggregate 'p' must be a number from 0 to 1, received 90` |
| `InvalidGroupKeyError` | `group_by` with a key that is not callable | `The group_by key must be callable, received 'department'` |
| `InvalidReportDefinitionError` | a JSON definition with the wrong shape | `Invalid report at $.aggregates[0]: missing 'at'` |

## Errors while a report runs

Whatever your `of`, `where`, group key or fold raises keeps its own type. pyaggregation only
adds an [exception note](https://docs.python.org/3/library/exceptions.html#BaseException.add_note)
naming the aggregate, such as `in aggregate 'payroll'`:

```python
from decimal import Decimal

from pyaggregation import total

try:
    total(lambda value: value, name="payroll")([Decimal(1), None])
except TypeError as error:
    assert error.__notes__ == ["in aggregate 'payroll'"]
```

## JSON-path notes

While compiling, errors from your injected compilers and from building aggregates keep their
type and get a note with the JSON path, such as `at $.aggregates[0].where`. See
[Report format](format.md#error-paths) for every path.
