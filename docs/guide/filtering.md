# Filtering and shares

## `where` filters each aggregate separately

`where` keeps only the items it returns something truthy for. Each aggregate has its own
`where`, so one pass can compare groups side by side:

```python
from pyaggregation import average, count

by_role = (
    average(salary, name="manager_average", where=is_manager)
    & average(salary, name="staff_average", where=lambda e: not e.manager)
    & count(name="well_paid", where=lambda e: e.salary >= 4000)
)

assert by_role(employees) == {
    "manager_average": Decimal("4000.00"),
    "staff_average": Decimal("3666.916666666666666666666667"),
    "well_paid": 3,
}
```

`where` runs **before** `of`, so `of` never sees an item it would fail on:

```python
from pyaggregation import total

bonuses = [Decimal("100"), None, Decimal("250")]

assert total(lambda bonus: bonus, name="bonuses", where=lambda bonus: bonus is not None)(
    bonuses
) == {"bonuses": Decimal("350")}
```

`where` must be callable; anything else raises `InvalidAggregateError` when the aggregate is
built.

## Reusable conditions

Any callable works as a condition, including a pyspecification `Predicate`, which composes
with `&`, `|` and `~`:

```python
from pyspecification import object_rule


@object_rule()
def earns_at_least(employee: Employee, amount: Decimal) -> bool:
    return employee.salary >= amount


senior = earns_at_least(Decimal(4000)) & ~earns_at_least(Decimal(5000))

assert count(name="senior", where=senior)(employees) == {"senior": 2}
```

## `share`: a part of the whole

`share` is the one aggregate where `where` does not filter: it splits the items into a part
(those `where` is true for) and the whole. Without `of` it is a share of items; with `of` it
is a share of the total of `of`.

```python
from pyaggregation import share

shares = share(name="of_people", where=is_manager) & share(
    name="of_payroll", where=is_manager, of=salary
)

assert shares(employees) == {
    "of_people": 0.4,
    "of_payroll": Decimal("0.4210360117363788271515598068"),
}
```

An empty or zero whole gives `None`:

```python
assert shares([]) == {"of_people": None, "of_payroll": None}
```

`where` is required for `share`.
