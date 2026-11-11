"""pyaggregation: Summaries over collections, computed in one pass.

`total(salary, name="payroll") & count(name="managers", where=is_manager)`
is a `Report`: several folds run together over any iterable, groupable by a key.
"""

from .aggregates import average, count, maximum, minimum, share, total
from .exceptions import (
    DuplicateResultNameError,
    InvalidAggregateError,
    InvalidGroupKeyError,
    InvalidResultNameError,
    PyaggregationError,
)
from .report import (
    Aggregate,
    Condition,
    Fold,
    GroupedReport,
    Report,
    Value,
    aggregate,
    identity,
)

__all__ = [
    "Aggregate",
    "Condition",
    "DuplicateResultNameError",
    "Fold",
    "GroupedReport",
    "InvalidAggregateError",
    "InvalidGroupKeyError",
    "InvalidResultNameError",
    "PyaggregationError",
    "Report",
    "Value",
    "aggregate",
    "average",
    "count",
    "identity",
    "maximum",
    "minimum",
    "share",
    "total",
]
