# Recipes

Complete, runnable programs for common jobs. Each one is self-contained.

## Sales dashboard per region

A shop shows a few KPI tiles per region from one pass over its orders.

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pyaggregation import average, count, count_distinct, maximum, percentile, share, total


@dataclass(frozen=True)
class Order:
    region: str
    customer: str
    amount: Decimal
    day: date
    refunded: bool = False


orders = [
    Order("North", "acme", Decimal("120.00"), date(2026, 11, 2)),
    Order("North", "globex", Decimal("80.00"), date(2026, 11, 3), refunded=True),
    Order("South", "acme", Decimal("200.00"), date(2026, 11, 3)),
    Order("North", "acme", Decimal("40.00"), date(2026, 11, 5)),
    Order("South", "initech", Decimal("60.00"), date(2026, 11, 7)),
]


def amount(order: Order) -> Decimal:
    return order.amount


def kept(order: Order) -> bool:
    return not order.refunded


dashboard = (
    total(amount, name="revenue", where=kept, start=Decimal(0))
    & count(name="orders", where=kept)
    & count_distinct(lambda order: order.customer, name="customers", where=kept)
    & average(amount, name="average_order", where=kept)
    & percentile(amount, name="p90_order", at=0.9, where=kept)
    & maximum(lambda order: order.day, name="last_order")
    & share(name="refund_rate", where=lambda order: order.refunded)
)

by_region = dashboard.group_by(lambda order: order.region)

assert by_region(orders)["North"] == {
    "revenue": Decimal("160.00"),
    "orders": 2,
    "customers": 1,
    "average_order": Decimal("80.00"),
    "p90_order": Decimal("112.000"),
    "last_order": date(2026, 11, 5),
    "refund_rate": 1 / 3,
}
assert dashboard(orders)["revenue"] == Decimal("420.00")
```

`where=kept` on each aggregate keeps refunds out of the money numbers while `refund_rate`
still sees every order.

## Monthly totals from a database cursor

Any iterable works, so rows can stream straight from a cursor without loading them all.

```python
import sqlite3
from decimal import Decimal

from pyaggregation import count, total

connection = sqlite3.connect(":memory:")
connection.execute("CREATE TABLE expenses (month TEXT, category TEXT, cents INTEGER)")
connection.executemany(
    "INSERT INTO expenses VALUES (?, ?, ?)",
    [
        ("2026-10", "travel", 12000),
        ("2026-10", "food", 3550),
        ("2026-11", "travel", 8000),
        ("2026-11", "food", 4200),
        ("2026-11", "food", 1800),
    ],
)

monthly = (
    total(lambda row: Decimal(row[2]) / 100, name="spent", start=Decimal(0))
    & count(name="receipts")
    & total(
        lambda row: Decimal(row[2]) / 100,
        name="food",
        where=lambda row: row[1] == "food",
        start=Decimal(0),
    )
).group_by(lambda row: row[0])

cursor = connection.execute("SELECT month, category, cents FROM expenses ORDER BY month")

assert monthly(cursor) == {
    "2026-10": {"spent": Decimal("155.5"), "receipts": 2, "food": Decimal("35.5")},
    "2026-11": {"spent": Decimal("140"), "receipts": 3, "food": Decimal("60")},
}
```

For a fixed summary over a large table, a SQL `GROUP BY` is faster; this shines when the
numbers are chosen at runtime or the rows need Python logic.

## A report builder API

Users pick their numbers in a UI. The server validates the request against the JSON Schema,
compiles it once and runs it.

```python
from dataclasses import dataclass
from decimal import Decimal

from jsonschema import Draft202012Validator

from pyaggregation import (
    InvalidReportDefinitionError,
    ReportCompiler,
    get_report_json_schema,
)


@dataclass(frozen=True)
class Ticket:
    team: str
    hours: Decimal
    priority: str
    open: bool


tickets = [
    Ticket("web", Decimal("2.5"), "high", open=True),
    Ticket("web", Decimal("1.0"), "low", open=False),
    Ticket("api", Decimal("4.0"), "high", open=False),
    Ticket("api", Decimal("0.5"), "low", open=True),
]


class Named:
    def __init__(self, **entries):
        self.entries = entries

    def compile(self, definition):
        return self.entries[definition]


VALUES = Named(hours=lambda ticket: ticket.hours, priority=lambda ticket: ticket.priority)
CONDITIONS = Named(open=lambda ticket: ticket.open, high=lambda ticket: ticket.priority == "high")
KEYS = Named(team=lambda ticket: ticket.team)

compiler = ReportCompiler(VALUES, CONDITIONS, KEYS, start=Decimal(0))
validator = Draft202012Validator(
    get_report_json_schema(
        {"enum": list(VALUES.entries)},
        {"enum": list(CONDITIONS.entries)},
        {"enum": list(KEYS.entries)},
    )
)


def run(request: dict) -> dict:
    if errors := [error.message for error in validator.iter_errors(request)]:
        return {"errors": errors}

    try:
        report = compiler.compile(request)
    except InvalidReportDefinitionError as error:
        return {"errors": [str(error)]}

    return {"data": report(tickets)}


response = run(
    {
        "aggregates": [
            {"name": "hours", "fold": "total", "of": "hours"},
            {"name": "open", "fold": "count", "where": "open"},
            {"name": "high_share", "fold": "share", "where": "high"},
        ],
        "group_by": "team",
    }
)

assert response == {
    "data": {
        "web": {"hours": Decimal("3.5"), "open": 1, "high_share": 0.5},
        "api": {"hours": Decimal("4.5"), "open": 1, "high_share": 0.5},
    }
}

assert "errors" in run({"aggregates": [{"name": "x", "fold": "median"}]})
```

## Grade statistics with a custom fold

A teacher wants the usual statistics plus a letter-grade histogram, still in one pass.

```python
from collections import Counter

from pyaggregation import Fold, aggregate, average, median, stdev


def letter(score: int) -> str:
    return "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "F"


def add_letter(acc: Counter[str], score: int) -> Counter[str]:
    acc[letter(score)] += 1

    return acc


histogram = Fold(Counter, add_letter, lambda acc: dict(sorted(acc.items())))

scores = [95, 82, 71, 88, 64, 90]

grades = (
    average(int, name="mean")
    & median(int, name="median")
    & stdev(int, name="stdev", sample=False)
    & aggregate(histogram, name="letters")
)

result = grades(scores)

assert result["mean"] == 81.66666666666667
assert result["median"] == 85.0
assert round(result["stdev"], 2) == 10.9
assert result["letters"] == {"A": 2, "B": 2, "C": 1, "F": 1}
```
