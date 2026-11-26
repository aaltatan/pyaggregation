# pyaggregation

**Summaries over collections, computed in one pass.**

Describe each number you want (a total, a count, an average, a percentile) as a small
aggregate, join them with `&`, and call the result with any iterable. You get one dict, one
loop over the data, and a definition you can also store as JSON and describe with JSON Schema.

```py
report = total(salary, name="payroll") & count(name="managers", where=is_manager)
```

## A first taste

A company wants a few headline numbers about its staff, overall and per department.

```python
from dataclasses import dataclass
from decimal import Decimal

from pyaggregation import average, count, median, total


@dataclass(frozen=True)
class Employee:
    name: str
    department: str
    salary: Decimal
    manager: bool = False


employees = [
    Employee("Alice", "Sales", Decimal("3000.00"), manager=True),
    Employee("Bob", "IT", Decimal("4500.50")),
    Employee("Carol", "Sales", Decimal("2500.25")),
    Employee("Dan", "IT", Decimal("5000.00"), manager=True),
    Employee("Eve", "IT", Decimal("4000.00")),
]


def salary(employee: Employee) -> Decimal:
    return employee.salary


def department(employee: Employee) -> str:
    return employee.department


def is_manager(employee: Employee) -> bool:
    return employee.manager


payroll = (
    total(salary, name="payroll", start=Decimal(0))
    & count(name="headcount")
    & count(name="managers", where=is_manager)
    & average(salary, name="average_salary")
    & median(salary, name="median_salary")
)

assert payroll(employees) == {
    "payroll": Decimal("19000.75"),
    "headcount": 5,
    "managers": 2,
    "average_salary": Decimal("3800.15"),
    "median_salary": Decimal("4000.00"),
}
```

Each built-in returned a one-result `Report`; `&` joined them into one report of five
results. Nothing is read until you call it, and then every employee is read exactly once.

### The same report per department

```python
by_department = payroll.group_by(department)

assert list(by_department(employees)) == ["Sales", "IT"]
assert by_department(employees)["Sales"]["payroll"] == Decimal("5500.25")
```

### Let users build the report as JSON

```python
from pyaggregation import ReportCompiler


class Named:
    def __init__(self, **entries):
        self.entries = entries

    def compile(self, definition):
        return self.entries[definition]


compiler = ReportCompiler(
    Named(salary=salary),
    Named(is_manager=is_manager),
    Named(department=department),
    start=Decimal(0),
)

report = compiler.compile(
    {
        "aggregates": [
            {"name": "payroll", "fold": "total", "of": "salary"},
            {"name": "managers", "fold": "count", "where": "is_manager"},
        ],
        "group_by": "department",
    }
)

assert report(employees)["IT"] == {"payroll": Decimal("13500.50"), "managers": 1}
```

## Where it fits

- **Dashboards and KPI tiles**: several numbers over the same records, in one pass.
- **Report builders**: users pick the numbers in a UI, the definition is saved as JSON.
- **Exports and API endpoints** that summarise records per customer, region or month.
- **Large or streamed input**: generators and database cursors are read only once.

**When not to use it.** If the data sits in a database and the summary is fixed, a SQL
`GROUP BY` is faster. For one number from a list, `sum()` is fine.

## Where to next

<div class="grid cards" markdown>

- [**Installation**](install.md): one command.
- [**User guide**](guide/index.md): every feature, one page each.
- [**Recipes**](recipes.md): complete real-world programs.
- [**Report format**](reference/format.md): the JSON shape of every fold.

</div>
