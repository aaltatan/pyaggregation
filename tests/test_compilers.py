import json
from decimal import Decimal

import pytest
from conftest import Employee, department, is_manager, salary
from pyformula import FormulaCompiler, variable
from pyspecification import Predicate, PredicateCompiler, RuleDoesNotExistError, object_rule

from pyaggregation import (
    DuplicateResultNameError,
    GroupedReport,
    InvalidReportDefinitionError,
    InvalidResultNameError,
    Report,
    ReportCompiler,
)


class Lookup:
    """A stand-in compiler: a definition is a key into a dict of callables."""

    def __init__(self, entries):
        self.entries = entries

    def compile(self, definition):
        return self.entries[definition]


VALUES = Lookup({"salary": salary, "name": lambda e: e.name})
CONDITIONS = Lookup({"is_manager": is_manager})
KEYS = Lookup({"department": department})


@pytest.fixture
def compiler():
    return ReportCompiler(VALUES, CONDITIONS, KEYS, start=Decimal(0))


def report(*aggregates, **extra):
    return {"aggregates": list(aggregates), **extra}


class TestCompiling:
    def test_every_fold_compiles(self, compiler, employees):
        compiled = compiler.compile(
            report(
                {"name": "payroll", "fold": "total", "of": "salary"},
                {"name": "managers", "fold": "count", "where": "is_manager"},
                {"name": "avg", "fold": "average", "of": "salary"},
                {"name": "manager_share", "fold": "share", "where": "is_manager"},
                {"name": "low", "fold": "minimum", "of": "salary"},
                {"name": "first", "fold": "maximum", "of": "name", "where": "is_manager"},
            )
        )

        assert repr(compiled) == "Report(payroll, managers, avg, manager_share, low, first)"

        assert compiled(employees) == {
            "payroll": Decimal("15000.75"),
            "managers": 2,
            "avg": Decimal("3750.1875"),
            "manager_share": 0.5,
            "low": Decimal("2500.25"),
            "first": "Dan",
        }

    def test_start_is_used_for_totals(self, compiler):
        compiled = compiler.compile(report({"name": "t", "fold": "total", "of": "salary"}))

        assert isinstance(compiled([])["t"], Decimal)

    def test_start_defaults_to_zero(self):
        compiled = ReportCompiler(VALUES, CONDITIONS).compile(
            report({"name": "t", "fold": "total", "of": "salary"})
        )

        assert compiled([]) == {"t": 0}

    def test_share_takes_an_optional_of(self, compiler, employees):
        compiled = compiler.compile(
            report({"name": "s", "fold": "share", "where": "is_manager", "of": "salary"})
        )

        assert compiled(employees)["s"] == Decimal("8000.00") / Decimal("15000.75")

    def test_group_by_returns_a_grouped_report(self, compiler, employees):
        compiled = compiler.compile(
            report({"name": "headcount", "fold": "count"}, group_by="department")
        )

        assert isinstance(compiled, GroupedReport)

        assert compiled(employees) == {"Sales": {"headcount": 2}, "IT": {"headcount": 2}}

    def test_without_group_by_returns_a_report(self, compiler):
        assert isinstance(compiler.compile(report({"name": "n", "fold": "count"})), Report)


class TestShapeErrors:
    @pytest.mark.parametrize(
        ("definition", "message"),
        [
            ([], r"Invalid report at \$: expected an object, received \[\]"),
            ({}, r"Invalid report at \$: missing 'aggregates'"),
            (
                {"aggregates": [], "extra": 1},
                r"Invalid report at \$: unknown 'extra'. Allowed keys: aggregates, group_by",
            ),
            (
                {"aggregates": []},
                r"Invalid report at \$.aggregates: expected a non-empty list, received \[\]",
            ),
            (
                {"aggregates": {"name": "n"}},
                r"Invalid report at \$.aggregates: expected a non-empty list",
            ),
            (
                report("count"),
                r"Invalid report at \$.aggregates\[0\]: expected an object, received 'count'",
            ),
            (
                report({"name": "n", "fold": "median"}),
                (
                    r"Invalid report at \$.aggregates\[0\].fold: unknown fold 'median'. "
                    r"Available folds: average, count, maximum, minimum, share, total"
                ),
            ),
            (
                report({"name": "n"}),
                r"Invalid report at \$.aggregates\[0\].fold: unknown fold None",
            ),
            (
                report({"name": "t", "fold": "total"}),
                r"Invalid report at \$.aggregates\[0\]: missing 'of'",
            ),
            (
                report({"name": "n", "fold": "count", "of": "salary"}),
                r"Invalid report at \$.aggregates\[0\]: unknown 'of'. Allowed keys: fold, name, where",
            ),
            (
                report({"name": "s", "fold": "share"}),
                r"Invalid report at \$.aggregates\[0\]: missing 'where'",
            ),
        ],
    )
    def test_reports_the_json_path(self, compiler, definition, message):
        with pytest.raises(InvalidReportDefinitionError, match=message):
            compiler.compile(definition)

    def test_group_by_needs_a_key_compiler(self):
        compiler = ReportCompiler(VALUES, CONDITIONS)

        with pytest.raises(
            InvalidReportDefinitionError,
            match=r"Invalid report at \$.group_by: grouping needs a key compiler",
        ):
            compiler.compile(report({"name": "n", "fold": "count"}, group_by="department"))


class TestLocatedErrors:
    def test_injected_compiler_errors_keep_their_type(self, compiler):
        with pytest.raises(KeyError) as caught:
            compiler.compile(report({"name": "n", "fold": "count", "where": "is_boss"}))

        assert caught.value.__notes__ == ["at $.aggregates[0].where"]

    def test_of_and_group_by_errors_are_located(self, compiler):
        with pytest.raises(KeyError) as caught:
            compiler.compile(report({"name": "n", "fold": "total", "of": "pay"}))

        assert caught.value.__notes__ == ["at $.aggregates[0].of"]

        with pytest.raises(KeyError) as caught:
            compiler.compile(report({"name": "n", "fold": "count"}, group_by="team"))

        assert caught.value.__notes__ == ["at $.group_by"]

    def test_invalid_names_are_located(self, compiler):
        with pytest.raises(InvalidResultNameError) as caught:
            compiler.compile(report({"name": "two words", "fold": "count"}))

        assert caught.value.__notes__ == ["at $.aggregates[0].name"]

    def test_duplicate_names_are_located(self, compiler):
        with pytest.raises(DuplicateResultNameError) as caught:
            compiler.compile(report({"name": "n", "fold": "count"}, {"name": "n", "fold": "count"}))

        assert caught.value.__notes__ == ["at $.aggregates"]


# --- with the family's real compilers


@variable()
def pay(employee: Employee) -> Decimal:
    return employee.salary


@object_rule()
def department__eq(employee: Employee, name: str) -> bool:
    return employee.department == name


REAL = """
{
  "aggregates": [
    {"name": "payroll", "fold": "total", "of": "pay"},
    {"name": "yearly", "fold": "total", "of": {"operator": "multiply", "expressions": ["pay", 12]}},
    {"name": "it", "fold": "count",
     "where": {"name": "department__eq", "args": ["IT"], "kwargs": {}, "inverse": false}}
  ]
}
"""


class TestWithPyformulaAndPyspecification:
    def test_compiles_and_runs(self, employees):
        compiler = ReportCompiler(
            FormulaCompiler[Employee]({"pay": pay}),
            PredicateCompiler[Employee, bool](
                {"department__eq": department__eq},
                lambda wrapper: Predicate(lambda _: wrapper["operator"] == "all"),
            ),
            start=Decimal(0),
        )

        compiled = compiler.compile(json.loads(REAL, parse_float=Decimal))

        assert compiled(employees) == {
            "payroll": Decimal("15000.75"),
            "yearly": Decimal("180009.00"),
            "it": 2,
        }

    def test_unknown_rule_points_at_the_aggregate(self):
        compiler = ReportCompiler(
            FormulaCompiler[Employee]({"pay": pay}),
            PredicateCompiler[Employee, bool]({}, lambda _: Predicate(lambda _: True)),
        )

        with pytest.raises(RuleDoesNotExistError) as caught:
            compiler.compile(json.loads(REAL))

        assert caught.value.__notes__[-1].startswith("at $.aggregates[2].where")
