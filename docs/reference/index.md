# Reference

- [API](api.md): every public name of `pyaggregation`.
- [Report format](format.md): the JSON shape of a report and every fold.
- [Exceptions](exceptions.md): the exception hierarchy and when each one is raised.

Everything in the API page is importable from the package root:

```python
import pyaggregation

assert sorted(pyaggregation.__all__) == [
    "Aggregate",
    "AggregateDict",
    "CONDITION_SCHEMA_ID",
    "Compiler",
    "Condition",
    "DuplicateResultNameError",
    "Fold",
    "GroupedReport",
    "InvalidAggregateError",
    "InvalidGroupKeyError",
    "InvalidReportDefinitionError",
    "InvalidResultNameError",
    "KEY_SCHEMA_ID",
    "PyaggregationError",
    "Report",
    "ReportCompiler",
    "ReportDict",
    "VALUE_SCHEMA_ID",
    "Value",
    "aggregate",
    "average",
    "collect",
    "count",
    "count_distinct",
    "every",
    "first",
    "get_report_json_schema",
    "identity",
    "join",
    "last",
    "maximum",
    "median",
    "minimum",
    "mode",
    "percentile",
    "product",
    "share",
    "some",
    "stdev",
    "total",
    "variance",
]
```
