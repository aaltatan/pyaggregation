"""The JSON Schema of a report definition, as accepted by `ReportCompiler.compile`.

pyaggregation does not know the languages inside `of`, `where` and `group_by`,
so their schemas are passed in, e.g. pyspecification's `get_expression_json_schema(rules)`.
"""

from collections.abc import Mapping
from typing import Any

from pyvocabulary import JSON_SCHEMA_DIALECT

from .compilers import FOLDS

VALUE_SCHEMA_ID = "urn:pyaggregation:value"
CONDITION_SCHEMA_ID = "urn:pyaggregation:condition"
KEY_SCHEMA_ID = "urn:pyaggregation:key"

_NAME_SCHEMA = {"type": "string", "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$"}
_FIELD_REFS = {"of": {"$ref": VALUE_SCHEMA_ID}, "where": {"$ref": CONDITION_SCHEMA_ID}}


def get_report_json_schema(
    value_schema: Mapping[str, Any],
    condition_schema: Mapping[str, Any],
    key_schema: Mapping[str, Any] | None = None,
    /,
) -> dict[str, Any]:
    """Return the JSON Schema of `{"aggregates": [{"name", "fold", "of", "where"}], "group_by"}`.

    Each fold has its own variant, so `of` and `where` are required or forbidden
    exactly as the compiler requires or forbids them. Each sub-schema is embedded
    under its own `$id`, so the `#/$defs/...` refs it uses keep pointing into itself.

    Args:
        value_schema: The schema of one `of`, e.g. a pyformula expression.
        condition_schema: The schema of one `where`, e.g. a pyspecification expression.
        key_schema: The schema of `group_by`. Without it, `group_by` is not allowed,
            matching a `ReportCompiler` without a key compiler.

    Example:
    ```python
    >>> schema = get_report_json_schema({"type": "string"}, {"type": "string"})
    >>> list(schema["properties"]), schema["$defs"]["count"]["required"]
    (['aggregates'], ['name', 'fold'])
    >>> schema["$defs"]["share"]["required"]
    ['name', 'fold', 'where']

    ```

    """
    defs: dict[str, Any] = {
        fold: _aggregate_schema(fold, required, optional)
        for fold, (required, optional) in FOLDS.items()
    }
    defs["value"] = {**value_schema, "$id": VALUE_SCHEMA_ID}
    defs["condition"] = {**condition_schema, "$id": CONDITION_SCHEMA_ID}

    properties: dict[str, Any] = {
        "aggregates": {
            "type": "array",
            "minItems": 1,
            "items": {"oneOf": [{"$ref": f"#/$defs/{fold}"} for fold in FOLDS]},
        },
    }

    if key_schema is not None:
        properties["group_by"] = {"$ref": KEY_SCHEMA_ID}
        defs["key"] = {**key_schema, "$id": KEY_SCHEMA_ID}

    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "type": "object",
        "properties": properties,
        "required": ["aggregates"],
        "additionalProperties": False,
        "$defs": defs,
    }


def _aggregate_schema(
    fold: str, required: frozenset[str], optional: frozenset[str]
) -> dict[str, Any]:
    fields = sorted(required | optional)

    return {
        "type": "object",
        "properties": {
            "name": _NAME_SCHEMA,
            "fold": {"const": fold},
            **{field: _FIELD_REFS[field] for field in fields},
        },
        "required": ["name", "fold", *sorted(required)],
        "additionalProperties": False,
    }
