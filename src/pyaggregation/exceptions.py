"""Exceptions raised by pyaggregation.

Errors raised while a report runs (by `of`, `where`, a key or a fold) keep their
own type; pyaggregation only adds a note naming the aggregate, e.g.
`in aggregate 'payroll'`.
"""

from collections.abc import Iterable

from pyvocabulary import InvalidNameError


class PyaggregationError(Exception):
    """Base class for every exception raised by pyaggregation."""


class InvalidResultNameError(PyaggregationError, InvalidNameError):
    """Raised when a result name is not a valid ASCII Python identifier."""

    def __init__(self, name: object, /) -> None:
        super().__init__(name, kind="result")


class DuplicateResultNameError(PyaggregationError, ValueError):
    """Raised when two aggregates of one report share a result name.

    Example:
    ```python
    >>> str(DuplicateResultNameError("payroll", ["payroll", "headcount"]))
    "Result name 'payroll' is used more than once. Result names: payroll, headcount"

    ```

    """

    def __init__(self, name: str, names: Iterable[str], /) -> None:
        super().__init__(
            f"Result name '{name}' is used more than once. Result names: {', '.join(names)}"
        )


class InvalidAggregateError(PyaggregationError, TypeError):
    """Raised when an aggregate or report is built from parts that cannot work."""


class InvalidGroupKeyError(PyaggregationError, TypeError):
    """Raised when `group_by` is given a key that is not callable."""


class InvalidReportDefinitionError(PyaggregationError, ValueError):
    """Raised when a JSON report definition does not have the expected shape."""
