# Money, Decimal and edge cases

## Values pass through unchanged

pyaggregation never converts or rounds values: `Decimal` stays `Decimal`, `int` sums stay
`int`.

```python
from pyaggregation import average, percentile, total

assert average(salary, name="average")(employees) == {"average": Decimal("3800.15")}
assert percentile(salary, name="p90", at=0.9)(employees) == {"p90": Decimal("4800.200")}
```

A float `at` such as `0.9` with `Decimal` values is read as the decimal `0.9`, so the
percentile stays exact.

Averaging integers gives a `float`, because that is what Python's `/` gives:

```python
assert average(len, name="mean")(["ab", "abcd"]) == {"mean": 3.0}
```

## `start` for money totals

Pass `start=Decimal(0)` to `total` so that an empty total is `Decimal('0')`, not the
integer `0`:

```python
assert total(salary, name="payroll")([]) == {"payroll": 0}
assert type(total(salary, name="payroll")([])["payroll"]) is int

empty = total(salary, name="payroll", start=Decimal(0))([])

assert type(empty["payroll"]) is Decimal
```

Mixing `Decimal` with `float` raises instead of quietly losing precision:

```python
try:
    total(lambda e: float(e.salary), name="payroll", start=Decimal(0))(employees)
except TypeError as error:
    assert error.__notes__ == ["in aggregate 'payroll'"]
```

## Rounding is your job

Round once, at the end, the way your domain requires:

```python
from decimal import ROUND_HALF_UP

result = average(salary, name="average", where=lambda e: not e.manager)(employees)

assert result["average"] == Decimal("3666.916666666666666666666667")
assert result["average"].quantize(Decimal("0.01"), ROUND_HALF_UP) == Decimal("3666.92")
```

## Empty or fully filtered input

A report always returns every key. Sums and collections give their empty value; everything
else gives `None`, never an exception or `NaN`:

```python
from pyaggregation import collect, count, join, median, product, stdev

everything = (
    total(salary, name="total", start=Decimal(0))
    & product(salary, name="product")
    & count(name="count")
    & average(salary, name="average")
    & median(salary, name="median")
    & stdev(salary, name="stdev")
    & collect(salary, name="collect")
    & join(lambda e: e.name, name="join")
)

assert everything([]) == {
    "total": Decimal("0"),
    "product": 1,
    "count": 0,
    "average": None,
    "median": None,
    "stdev": None,
    "collect": [],
    "join": "",
}

assert everything(employees[:1])["stdev"] is None  # a sample stdev needs two values
```

## `None` values are not skipped

Unlike SQL's `NULL`, a `None` is a value. Arithmetic on it fails, with a note naming the
aggregate:

```python
bonuses = [Decimal("100"), None, Decimal("250")]

try:
    total(lambda bonus: bonus, name="bonuses")(bonuses)
except TypeError as error:
    assert error.__notes__ == ["in aggregate 'bonuses'"]
```

Skip them explicitly with `where`:

```python
assert total(lambda bonus: bonus, name="bonuses", where=lambda bonus: bonus is not None)(
    bonuses
) == {"bonuses": Decimal("350")}
```

Aggregates that do not compute, such as `first`, `collect` and `count_distinct`, treat
`None` as an ordinary value.

## Errors keep their type

Whatever `of`, `where`, a group key or a fold raises while a report runs comes through
unchanged, with only an `in aggregate '...'` note added, so your `except` clauses still
work:

```python
def strict_salary(employee: Employee) -> Decimal:
    if employee.salary <= 0:
        msg = f"{employee.name} has no salary"
        raise ValueError(msg)

    return employee.salary


try:
    total(strict_salary, name="payroll")([Employee("Zed", "IT", Decimal(0))])
except ValueError as error:
    assert str(error) == "Zed has no salary"
    assert error.__notes__ == ["in aggregate 'payroll'"]
```
