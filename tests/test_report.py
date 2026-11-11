import operator
import re
from decimal import Decimal

import pytest
from conftest import department, is_manager, salary

from pyaggregation import (
    Aggregate,
    DuplicateResultNameError,
    Fold,
    InvalidAggregateError,
    InvalidGroupKeyError,
    InvalidResultNameError,
    PyaggregationError,
    Report,
    aggregate,
    count,
    total,
)


def collect():
    return Fold(list, lambda acc, value: [*acc, value], tuple)


class TestAggregate:
    def test_custom_fold_sees_values_from_of(self, employees):
        names = aggregate(collect(), name="names", of=lambda e: e.name)

        assert names(employees) == {"names": ("Alice", "Bob", "Carol", "Dan")}

    def test_of_defaults_to_the_item_itself(self):
        assert aggregate(collect(), name="items")([1, 2]) == {"items": (1, 2)}

    def test_where_filters_before_of_runs(self):
        halves = aggregate(collect(), name="halves", of=lambda n: 1 / n, where=bool)

        assert halves([0, 2, 4]) == {"halves": (0.5, 0.25)}

    def test_initial_is_called_per_run(self):
        names = aggregate(collect(), name="names")

        assert names([1]) == {"names": (1,)}

        assert names([2]) == {"names": (2,)}

    @pytest.mark.parametrize("name", ["", "two words", "1st", None])
    def test_rejects_invalid_names(self, name):
        with pytest.raises(InvalidResultNameError, match="Invalid result name"):
            aggregate(collect(), name=name)

    def test_rejects_a_fold_that_is_not_a_fold(self):
        with pytest.raises(InvalidAggregateError, match="'items' must have a Fold"):
            Aggregate("items", sum)  # type: ignore[arg-type]

    @pytest.mark.parametrize("role", ["of", "where"])
    def test_rejects_non_callables(self, role):
        with pytest.raises(InvalidAggregateError, match="'items' must be callable, received 3"):
            aggregate(collect(), name="items", **{role: 3})

    def test_errors_keep_their_type_and_name_the_aggregate(self):
        broken = aggregate(Fold(int, operator.add, int), name="broken", of=lambda _: "x")

        with pytest.raises(TypeError) as caught:
            broken([1])

        assert "in aggregate 'broken'" in caught.value.__notes__

    def test_errors_in_finish_name_the_aggregate(self):
        broken = aggregate(Fold(int, operator.add, lambda acc: 1 / acc), name="broken")

        with pytest.raises(ZeroDivisionError) as caught:
            broken([])

        assert caught.value.__notes__ == ["in aggregate 'broken'"]


class TestReport:
    def test_and_joins_results_in_order(self, employees):
        report = total(salary, name="payroll") & count(name="managers", where=is_manager)

        assert report(employees) == {"payroll": Decimal("15000.75"), "managers": 2}

    def test_reads_the_input_once(self, employees):
        report = total(salary, name="payroll") & count(name="headcount")

        assert report(iter(employees)) == {"payroll": Decimal("15000.75"), "headcount": 4}

    def test_and_returns_a_new_report(self):
        payroll = total(salary, name="payroll")

        joined = payroll & count(name="headcount")

        assert len(payroll.aggregates) == 1

        assert len(joined.aggregates) == 2

    def test_and_with_something_else_is_a_type_error(self):
        with pytest.raises(TypeError):
            total(salary, name="payroll") & 1  # type: ignore[operator]

    def test_rejects_duplicate_names_when_built(self):
        with pytest.raises(
            DuplicateResultNameError,
            match=re.escape(
                "Result name 'payroll' is used more than once. Result names: payroll, headcount"
            ),
        ):
            total(salary, name="payroll") & count(name="headcount") & count(name="payroll")

    def test_rejects_an_empty_report(self):
        with pytest.raises(InvalidAggregateError, match="at least one aggregate"):
            Report(())

    def test_repr_lists_result_names(self):
        report = total(salary, name="payroll") & count(name="headcount")

        assert repr(report) == "Report(payroll, headcount)"

    def test_errors_share_a_base_class(self):
        assert issubclass(DuplicateResultNameError, PyaggregationError)

        assert issubclass(InvalidResultNameError, ValueError)


class TestGroupedReport:
    def test_groups_in_first_seen_order(self, employees):
        report = (total(salary, name="payroll") & count(name="headcount")).group_by(department)

        assert report(iter(employees)) == {
            "Sales": {"payroll": Decimal("5500.25"), "headcount": 2},
            "IT": {"payroll": Decimal("9500.50"), "headcount": 2},
        }

    def test_tuple_keys_group_by_several_fields(self, employees):
        report = count(name="headcount").group_by(lambda e: (e.department, e.manager))

        assert report(employees)[("Sales", True)] == {"headcount": 1}

    def test_empty_input_has_no_groups(self):
        assert count(name="headcount").group_by(department)([]) == {}

    def test_leaves_the_report_unchanged(self, employees):
        report = count(name="headcount")

        report.group_by(department)

        assert report(employees) == {"headcount": 4}

    def test_rejects_a_key_that_is_not_callable(self):
        with pytest.raises(InvalidGroupKeyError, match="must be callable, received 'department'"):
            count(name="headcount").group_by("department")  # type: ignore[arg-type]

    def test_repr_names_the_key(self):
        report = count(name="headcount").group_by(department)

        assert repr(report) == "Report(headcount).group_by(department)"
