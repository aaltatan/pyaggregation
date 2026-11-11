from dataclasses import dataclass
from decimal import Decimal

import pytest


@dataclass(frozen=True, slots=True)
class Employee:
    name: str
    department: str
    salary: Decimal
    manager: bool = False


EMPLOYEES = (
    Employee("Alice", "Sales", Decimal("3000.00"), manager=True),
    Employee("Bob", "IT", Decimal("4500.50")),
    Employee("Carol", "Sales", Decimal("2500.25")),
    Employee("Dan", "IT", Decimal("5000.00"), manager=True),
)


def salary(employee: Employee) -> Decimal:
    return employee.salary


def department(employee: Employee) -> str:
    return employee.department


def is_manager(employee: Employee) -> bool:
    return employee.manager


@pytest.fixture
def employees() -> tuple[Employee, ...]:
    return EMPLOYEES
