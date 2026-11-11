# pyaggregation

**In development.** Summaries over collections, computed in one pass and definable as JSON.

```python
report = (
    total(salary, name="payroll")
    & average(salary, name="average_salary")
    & count(name="managers", where=is_manager)
)
report(employees)  # {'payroll': ..., 'average_salary': ..., 'managers': 2}
report.group_by(department)(employees)  # one dict per department
```

Built-ins: `total`, `product`, `count`, `count_distinct`, `average`, `share`, `variance`,
`stdev`, `minimum`, `maximum`, `median`, `percentile`, `mode`, `first`, `last`, `some`, `every`,
`collect`, `join`; `aggregate(fold, ...)` adds your own. See `docs/DESIGN.md` for the rules
(empty input, `Decimal`, memory).

The name `pyaggregate` is taken on PyPI. See `PHASES.md` for the plan.
