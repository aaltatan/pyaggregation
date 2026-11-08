"""pyaggregation: Summaries over collections, computed in one pass.

`total(salary, name="payroll") & count(name="managers", where=is_manager())`
is a `Report`: several folds run together over any iterable, groupable by a key.

Nothing is implemented yet; see PHASES.md for the plan.
"""

__all__: list[str] = []
