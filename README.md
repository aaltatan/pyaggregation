# pyaggregation

**Planned.** Summaries over collections, computed in one pass and definable as JSON.

```python
report = (
    total(salary, name="payroll")
    & average(salary, name="average_salary")
    & count(name="managers", where=is_manager())
)
report(employees)                         # {'payroll': ..., 'average_salary': ..., 'managers': 2}
report.group_by(department)(employees)    # one dict per department
```

The name `pyaggregate` is taken on PyPI. See `PHASES.md` for the plan.
