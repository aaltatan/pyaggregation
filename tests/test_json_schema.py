import pytest
from jsonschema import Draft202012Validator

from pyaggregation import get_report_json_schema

# Like pyspecification's schemas, this one uses its own `#/$defs` refs internally.
CONDITION_SCHEMA = {
    "$defs": {"rule": {"enum": ["is_manager"]}},
    "$ref": "#/$defs/rule",
}
VALUE_SCHEMA = {"enum": ["salary"]}
KEY_SCHEMA = {"enum": ["department"]}


def validator(*, keys=True):
    schema = get_report_json_schema(VALUE_SCHEMA, CONDITION_SCHEMA, KEY_SCHEMA if keys else None)

    return Draft202012Validator(schema)


def valid(definition, *, keys=True):
    return validator(keys=keys).is_valid(definition)


def report(*aggregates, **extra):
    return {"aggregates": list(aggregates), **extra}


class TestReportJsonSchema:
    def test_is_a_valid_2020_12_schema(self):
        Draft202012Validator.check_schema(validator().schema)

    def test_accepts_every_fold(self):
        assert valid(
            report(
                {"name": "payroll", "fold": "total", "of": "salary"},
                {"name": "managers", "fold": "count", "where": "is_manager"},
                {"name": "avg", "fold": "average", "of": "salary", "where": "is_manager"},
                {"name": "share", "fold": "share", "where": "is_manager", "of": "salary"},
                {"name": "low", "fold": "minimum", "of": "salary"},
                {"name": "high", "fold": "maximum", "of": "salary"},
            ),
            keys=False,
        )

    @pytest.mark.parametrize(
        "aggregate",
        [
            {"name": "t", "fold": "total"},
            {"name": "n", "fold": "count", "of": "salary"},
            {"name": "s", "fold": "share"},
            {"name": "n", "fold": "median", "of": "salary"},
            {"name": "two words", "fold": "count"},
            {"fold": "count"},
            {"name": "n", "fold": "count", "where": "is_boss"},
            {"name": "t", "fold": "total", "of": "pay"},
        ],
    )
    def test_rejects_what_the_compiler_rejects(self, aggregate):
        assert not valid(report(aggregate))

    def test_rejects_an_empty_report(self):
        assert not valid(report())

    def test_group_by_needs_a_key_schema(self):
        grouped = report({"name": "n", "fold": "count"}, group_by="department")

        assert valid(grouped)

        assert not valid(grouped, keys=False)

        assert not valid({**grouped, "group_by": "team"})

    def test_embedded_schemas_keep_their_own_refs(self):
        schema = validator().schema

        assert schema["$defs"]["condition"]["$id"] == "urn:pyaggregation:condition"
