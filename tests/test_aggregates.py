from decimal import Decimal

import pytest
from conftest import is_manager, salary

from pyaggregation import (
    InvalidAggregateError,
    average,
    count,
    maximum,
    minimum,
    share,
    total,
)


class TestTotal:
    def test_sums_values(self, employees):
        assert total(salary, name="payroll")(employees) == {"payroll": Decimal("15000.75")}

    def test_where_filters(self, employees):
        report = total(salary, name="managers_pay", where=is_manager)

        assert report(employees) == {"managers_pay": Decimal("8000.00")}

    def test_empty_input_is_start(self):
        assert total(salary, name="payroll")([]) == {"payroll": 0}

        result = total(salary, name="payroll", start=Decimal(0))([])["payroll"]

        assert isinstance(result, Decimal)

    def test_mixing_decimal_and_float_raises(self):
        with pytest.raises(TypeError):
            total(float, name="t", start=Decimal(0))([1.5])


class TestCount:
    def test_counts_items(self, employees):
        assert count(name="headcount")(employees) == {"headcount": 4}

    def test_counts_items_that_pass_where(self, employees):
        assert count(name="managers", where=is_manager)(employees) == {"managers": 2}

    def test_empty_input_is_zero(self):
        assert count(name="headcount")([]) == {"headcount": 0}


class TestAverage:
    def test_decimal_values_stay_decimal(self, employees):
        result = average(salary, name="avg")(employees)["avg"]

        assert result == Decimal("3750.1875")

    def test_ints_divide_to_float(self):
        assert average(int, name="avg")([1, 2]) == {"avg": 1.5}

    def test_empty_or_filtered_out_is_none(self, employees):
        assert average(salary, name="avg")([]) == {"avg": None}

        assert average(salary, name="avg", where=lambda _: False)(employees) == {"avg": None}


class TestShare:
    def test_share_of_items(self, employees):
        assert share(name="managers", where=is_manager)(employees) == {"managers": 0.5}

    def test_share_of_a_total(self, employees):
        result = share(name="pay", where=is_manager, of=salary)(employees)["pay"]

        assert result == Decimal("8000.00") / Decimal("15000.75")

    def test_no_match_is_zero(self, employees):
        assert share(name="none", where=lambda _: False)(employees) == {"none": 0}

    def test_empty_or_zero_whole_is_none(self):
        assert share(name="s", where=bool)([]) == {"s": None}

        assert share(name="s", where=bool, of=int)([0, 0]) == {"s": None}

    def test_rejects_a_where_that_is_not_callable(self):
        with pytest.raises(InvalidAggregateError, match="'s' must be callable"):
            share(name="s", where=None)  # type: ignore[arg-type]


class TestMinimumAndMaximum:
    def test_smallest_and_largest_values(self, employees):
        report = minimum(salary, name="low") & maximum(salary, name="high")

        assert report(employees) == {"low": Decimal("2500.25"), "high": Decimal("5000.00")}

    def test_where_filters(self, employees):
        report = minimum(salary, name="low", where=is_manager)

        assert report(employees) == {"low": Decimal("3000.00")}

    def test_empty_input_is_none(self):
        report = minimum(salary, name="low") & maximum(salary, name="high")

        assert report([]) == {"low": None, "high": None}
