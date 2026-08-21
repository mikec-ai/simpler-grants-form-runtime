import pytest

from src.form_schema.components.schema_field_list import (
    SchemaFieldListError,
    build_schema_field_list,
)


def test_builds_nested_native_field_lists_without_a_custom_widget() -> None:
    schema = {
        "type": "array",
        "minItems": 1,
        "maxItems": 5,
        "items": {
            "type": "object",
            "title": "Period",
            "properties": {
                "name": {"type": "string"},
                "total": {"type": "string", "readOnly": True},
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "title": "Row",
                        "properties": {"amount": {"type": "string"}},
                    },
                },
            },
        },
    }

    result = build_schema_field_list(
        schema,
        definition="/properties/periods",
        name="periods",
        label="Budget Period",
    )

    assert result.array_definitions == (
        "/properties/periods",
        "/properties/periods/items/properties/rows",
    )
    assert result.leaf_definitions == (
        "/properties/periods/items/properties/name",
        "/properties/periods/items/properties/total",
        "/properties/periods/items/properties/rows/items/properties/amount",
    )
    assert result.ui_schema["children"][1]["type"] == "null"
    assert result.ui_schema["children"][2] == {
        "type": "fieldList",
        "name": "rows",
        "label": "Row",
        "definition": "/properties/periods/items/properties/rows",
        "children": [
            {
                "type": "field",
                "definition": "/properties/periods/items/properties/rows/items/properties/amount",
            }
        ],
    }


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {}},
        {"type": "array", "items": {"type": "string"}},
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"values": {"type": "array", "items": {"type": "string"}}},
            },
        },
    ],
)
def test_rejects_shapes_outside_the_native_object_field_list_contract(schema: dict) -> None:
    with pytest.raises(SchemaFieldListError):
        build_schema_field_list(
            schema,
            definition="/properties/periods",
            name="periods",
            label="Budget Period",
        )
