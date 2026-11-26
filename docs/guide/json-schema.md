# JSON Schema

`get_report_json_schema` describes exactly what `ReportCompiler.compile` accepts, for form
builders, editor autocompletion or request validation.

```py
get_report_json_schema(value_schema, condition_schema, key_schema=None, /) -> dict
```

Pass the schemas of your `of`, `where` and (optionally) `group_by` languages. Each is
embedded under its own `$id`, so the `#/$defs/...` refs inside it keep pointing into itself.

```python
from pyaggregation import (
    CONDITION_SCHEMA_ID,
    KEY_SCHEMA_ID,
    VALUE_SCHEMA_ID,
    get_report_json_schema,
)

schema = get_report_json_schema(
    {"enum": ["salary"]},
    {"enum": ["is_manager"]},
    {"enum": ["department"]},
)

assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
assert schema["required"] == ["aggregates"]
assert list(schema["properties"]) == ["aggregates", "group_by"]
assert schema["properties"]["aggregates"]["minItems"] == 1

assert schema["$defs"]["value"] == {"enum": ["salary"], "$id": VALUE_SCHEMA_ID}
assert schema["$defs"]["condition"]["$id"] == CONDITION_SCHEMA_ID
assert schema["$defs"]["key"]["$id"] == KEY_SCHEMA_ID
```

## One variant per fold

Each fold has its own entry in `$defs`, so `of`, `where` and options such as `at` are
required or forbidden exactly as the compiler requires or forbids them:

```python
assert schema["$defs"]["percentile"]["required"] == ["name", "fold", "at", "of"]
assert schema["$defs"]["percentile"]["properties"]["at"] == {
    "type": "number",
    "minimum": 0,
    "maximum": 1,
}
assert schema["$defs"]["count"]["required"] == ["name", "fold"]
assert "of" not in schema["$defs"]["count"]["properties"]
assert schema["$defs"]["share"]["required"] == ["name", "fold", "where"]
assert schema["$defs"]["percentile"]["additionalProperties"] is False
```

## Without grouping

Without `key_schema`, `group_by` is not allowed, matching a `ReportCompiler` without a key
compiler:

```python
ungrouped = get_report_json_schema({"type": "string"}, {"type": "string"})

assert list(ungrouped["properties"]) == ["aggregates"]
assert ungrouped["additionalProperties"] is False
assert "key" not in ungrouped["$defs"]
```

## Validating a request

Any JSON Schema 2020-12 validator works, for example
[jsonschema](https://pypi.org/project/jsonschema/):

```python
from jsonschema import Draft202012Validator

validator = Draft202012Validator(schema)

assert validator.is_valid(
    {
        "aggregates": [{"name": "payroll", "fold": "total", "of": "salary"}],
        "group_by": "department",
    }
)
assert not validator.is_valid({"aggregates": [{"name": "p", "fold": "percentile", "of": "salary"}]})
```

## With pyformula and pyspecification

Their schema functions plug straight in. pyspecification's `get_expression_json_schema`
takes the same rules you give `PredicateCompiler`, and its internal `#/$defs` refs keep
working once embedded:

```python
from pyspecification import get_expression_json_schema, object_rule


@object_rule()
def department__eq(employee: Employee, name: str) -> bool:
    return employee.department == name


schema = get_report_json_schema(
    {"enum": ["pay"]},
    get_expression_json_schema({"department__eq": department__eq}),
)

assert Draft202012Validator(schema).is_valid(
    {
        "aggregates": [
            {
                "name": "it",
                "fold": "count",
                "where": {"name": "department__eq", "args": ["IT"], "kwargs": {}, "inverse": False},
            }
        ]
    }
)
```

For values, recent pyformula releases provide `get_formula_json_schema(registry.variables)`,
which fits the `value_schema` slot the same way.
