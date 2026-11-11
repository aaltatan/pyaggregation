import statistics
from decimal import Decimal

import pytest
from conftest import department, is_manager, salary

from pyaggregation import (
    InvalidAggregateError,
    average,
    collect,
    count,
    count_distinct,
    every,
    first,
    identity,
    join,
    last,
    maximum,
    median,
    minimum,
    mode,
    percentile,
    product,
    share,
    some,
    stdev,
    total,
    variance,
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

    def test_none_values_are_not_skipped(self):
        with pytest.raises(TypeError) as caught:
            minimum(identity, name="low")([1, None])

        assert caught.value.__notes__ == ["in aggregate 'low'"]

    def test_none_as_first_value_is_not_mistaken_for_no_value(self):
        with pytest.raises(TypeError):
            maximum(identity, name="high")([None, 1])

    def test_zero_and_negative_values(self):
        report = minimum(int, name="low") & maximum(int, name="high")

        assert report([0, -3, 0]) == {"low": -3, "high": 0}


class TestVarianceAndStdev:
    VALUES = (2, 4, 4, 4, 5, 5, 7, 9)

    def test_sample_by_default_like_statistics(self):
        result = (variance(int, name="var") & stdev(int, name="sd"))(self.VALUES)

        assert result["var"] == pytest.approx(statistics.variance(self.VALUES))

        assert result["sd"] == pytest.approx(statistics.stdev(self.VALUES))

    def test_population_when_sample_is_false(self):
        report = variance(int, name="var", sample=False) & stdev(int, name="sd", sample=False)

        assert report(self.VALUES) == pytest.approx({"var": 4.0, "sd": 2.0})

    def test_decimal_values_stay_decimal(self):
        values = [Decimal(1), Decimal(2), Decimal(3)]

        result = (variance(Decimal, name="var") & stdev(Decimal, name="sd"))(values)

        assert result == {"var": Decimal(1), "sd": Decimal(1)}

        assert all(isinstance(value, Decimal) for value in result.values())

    def test_large_offsets_stay_accurate(self):
        values = [1e9 + 4, 1e9 + 7, 1e9 + 13, 1e9 + 16]

        assert variance(float, name="var")(values)["var"] == pytest.approx(30)

    def test_too_few_values_is_none(self):
        assert variance(int, name="v")([]) == {"v": None}

        assert variance(int, name="v")([5]) == {"v": None}

        assert stdev(int, name="v", sample=False)([]) == {"v": None}

        assert stdev(int, name="v", sample=False)([5]) == {"v": 0}

    def test_where_filters(self, employees):
        report = variance(salary, name="v", where=is_manager, sample=False)

        assert report(employees) == {"v": Decimal(1000000)}

    def test_rejects_a_non_boolean_sample(self):
        with pytest.raises(InvalidAggregateError, match="sample of aggregate 'v' must be a bool"):
            variance(int, name="v", sample="yes")  # type: ignore[arg-type]


class TestFirstAndLast:
    def test_first_and_last_in_input_order(self, employees):
        report = first(lambda e: e.name, name="a") & last(lambda e: e.name, name="z")

        assert report(employees) == {"a": "Alice", "z": "Dan"}

    def test_where_filters(self, employees):
        report = first(lambda e: e.name, name="a", where=lambda e: not e.manager)

        assert report(employees) == {"a": "Bob"}

    def test_none_is_a_real_value(self):
        report = first(identity, name="a") & last(identity, name="z")

        assert report([None, 1, None]) == {"a": None, "z": None}

        assert report([1, None, 2]) == {"a": 1, "z": 2}

    def test_empty_input_is_none(self):
        assert (first(int, name="a") & last(int, name="z"))([]) == {"a": None, "z": None}


class TestSomeAndEvery:
    def test_truthiness_of_values(self, employees):
        report = some(is_manager, name="any") & every(is_manager, name="all")

        assert report(employees) == {"any": True, "all": False}

    def test_where_filters(self, employees):
        report = every(is_manager, name="all", where=lambda e: e.salary >= 3000)

        assert report(employees) == {"all": False}

        report = every(is_manager, name="all", where=lambda e: e.salary == 5000)

        assert report(employees) == {"all": True}

    def test_falsy_values_count_as_false(self):
        report = some(identity, name="any") & every(identity, name="all")

        assert report([0, "", None]) == {"any": False, "all": False}

        assert report([1, "x"]) == {"any": True, "all": True}

    def test_empty_input_is_none_not_vacuous_truth(self):
        report = some(identity, name="any") & every(identity, name="all")

        assert report([]) == {"any": None, "all": None}


class TestProduct:
    def test_multiplies_values(self):
        assert product(int, name="p")([2, 3, 4]) == {"p": 24}

    def test_zero_wins(self):
        assert product(int, name="p")([2, 0, 4]) == {"p": 0}

    def test_empty_input_is_start(self):
        assert product(int, name="p")([]) == {"p": 1}

        result = product(Decimal, name="p", start=Decimal(1))([])["p"]

        assert isinstance(result, Decimal)

    def test_decimal_stays_exact(self):
        assert product(Decimal, name="p")(["1.1", "1.1", "1.1"]) == {"p": Decimal("1.331")}


class TestCountDistinct:
    def test_counts_unique_values(self, employees):
        assert count_distinct(department, name="d")(employees) == {"d": 2}

    def test_equal_numbers_of_different_types_are_one_value(self):
        assert count_distinct(identity, name="d")([1, 1.0, Decimal(1), True]) == {"d": 1}

    def test_none_is_a_value(self):
        assert count_distinct(identity, name="d")([None, None, 0]) == {"d": 2}

    def test_empty_input_is_zero(self):
        assert count_distinct(identity, name="d")([]) == {"d": 0}

    def test_unhashable_values_name_the_aggregate(self):
        with pytest.raises(TypeError) as caught:
            count_distinct(identity, name="d")([[1]])

        assert caught.value.__notes__ == ["in aggregate 'd'"]


class TestMedianAndPercentile:
    def test_odd_count_is_the_middle_value(self):
        assert median(int, name="m")([5, 1, 3]) == {"m": 3}

    def test_even_count_is_the_mean_of_the_middle_two(self):
        assert median(int, name="m")([4, 1, 3, 2]) == {"m": 2.5}

    def test_decimal_stays_decimal(self):
        result = median(Decimal, name="m")(["1.10", "1.20"])["m"]

        assert result == Decimal("1.15")

        assert isinstance(result, Decimal)

    def test_single_value_and_empty_input(self):
        assert median(int, name="m")([7]) == {"m": 7}

        assert median(int, name="m")([]) == {"m": None}

    def test_percentile_interpolates_linearly(self):
        report = (
            percentile(int, name="p0", at=0)
            & percentile(int, name="p90", at=0.9)
            & percentile(int, name="p100", at=1)
        )

        result = report(range(10, 0, -1))

        assert result["p0"] == 1

        assert result["p90"] == pytest.approx(9.1)

        assert result["p100"] == 10

    def test_percentile_of_decimals_with_a_float_at_stays_exact(self):
        result = percentile(Decimal, name="p", at=0.25)(["10", "20"])["p"]

        assert result == Decimal("12.5")

        assert isinstance(result, Decimal)

    def test_percentile_of_one_value_is_that_value(self):
        assert percentile(int, name="p", at=0.9)([4]) == {"p": 4}

    def test_unsortable_values_name_the_aggregate(self):
        with pytest.raises(TypeError) as caught:
            median(identity, name="m")([1, "a"])

        assert caught.value.__notes__ == ["in aggregate 'm'"]

    @pytest.mark.parametrize("at", [-0.1, 1.5, "half", None, True, float("nan")])
    def test_rejects_at_outside_zero_to_one(self, at):
        with pytest.raises(InvalidAggregateError, match="at of aggregate 'p' must be a number"):
            percentile(int, name="p", at=at)

    def test_each_run_starts_empty(self):
        report = median(int, name="m")

        assert report([1, 2, 3]) == {"m": 2}

        assert report([10]) == {"m": 10}


class TestMode:
    def test_most_common_value(self):
        assert mode(identity, name="m")([1, 2, 2, 3]) == {"m": 2}

    def test_ties_go_to_the_first_seen(self):
        assert mode(identity, name="m")([3, 1, 1, 3]) == {"m": 3}

    def test_works_for_strings(self, employees):
        assert mode(department, name="m")(employees) == {"m": "Sales"}

    def test_empty_input_is_none(self):
        assert mode(identity, name="m")([]) == {"m": None}


class TestCollectAndJoin:
    def test_collect_keeps_values_in_order(self, employees):
        report = collect(lambda e: e.name, name="names", where=is_manager)

        assert report(employees) == {"names": ["Alice", "Dan"]}

    def test_collect_starts_fresh_each_run(self):
        report = collect(identity, name="c")

        assert report([1]) == {"c": [1]}

        assert report([2]) == {"c": [2]}

        assert report([]) == {"c": []}

    def test_join_with_a_separator(self, employees):
        names = join(lambda e: e.name, name="n") & join(lambda e: e.name, name="s", separator="/")

        assert names(employees) == {"n": "Alice, Bob, Carol, Dan", "s": "Alice/Bob/Carol/Dan"}

    def test_join_of_nothing_is_empty(self):
        assert join(str, name="n")([]) == {"n": ""}

    def test_join_needs_strings(self):
        with pytest.raises(TypeError) as caught:
            join(identity, name="n")(["a", 1])

        assert caught.value.__notes__ == ["in aggregate 'n'"]

    def test_rejects_a_non_string_separator(self):
        with pytest.raises(InvalidAggregateError, match="separator of aggregate 'n' must be a str"):
            join(str, name="n", separator=1)  # type: ignore[arg-type]
