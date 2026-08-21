from dataclasses import dataclass
from typing import Any


class SchemaFieldListError(ValueError):
    """Raised when a reviewed object-array cannot use the native FieldList contract."""


@dataclass(frozen=True)
class SchemaFieldListDefinition:
    ui_schema: dict[str, Any]
    leaf_definitions: tuple[str, ...]
    array_definitions: tuple[str, ...]


def build_schema_field_list(
    schema: dict[str, Any],
    *,
    definition: str,
    name: str,
    label: str,
    attachment_definitions: frozenset[str] = frozenset(),
) -> SchemaFieldListDefinition:
    """Project one reviewed array-of-objects through Simpler's native FieldList.

    This is deliberately structural: it does not infer semantics, conditions, or
    calculations. Plain objects are flattened, nested arrays become nested
    FieldLists, and explicitly supplied attachment pointers receive that widget.
    """

    if schema.get("type") != "array" or not isinstance(schema.get("items"), dict):
        raise SchemaFieldListError(f"FieldList {definition} must resolve to an array")
    if schema["items"].get("type") != "object":
        raise SchemaFieldListError(f"FieldList {definition} items must be objects")

    leaves: list[str] = []
    arrays: list[str] = [definition]

    def children_for_object(node: dict[str, Any], pointer: str) -> list[dict[str, Any]]:
        if node.get("type") != "object" or not isinstance(node.get("properties"), dict):
            raise SchemaFieldListError(f"Expected an object schema at {pointer}")
        children: list[dict[str, Any]] = []
        for property_name, child in node["properties"].items():
            if not isinstance(child, dict):
                raise SchemaFieldListError(
                    f"Invalid schema at {pointer}/properties/{property_name}"
                )
            child_pointer = f"{pointer}/properties/{property_name}"
            child_type = child.get("type")
            if child_type == "object":
                children.extend(children_for_object(child, child_pointer))
            elif child_type == "array":
                items = child.get("items")
                if not isinstance(items, dict) or items.get("type") != "object":
                    raise SchemaFieldListError(
                        f"Nested FieldList {child_pointer} must contain object items"
                    )
                arrays.append(child_pointer)
                children.append(
                    {
                        "type": "fieldList",
                        "name": property_name,
                        "label": items.get("title") or child.get("title") or property_name,
                        "definition": child_pointer,
                        "children": children_for_object(items, f"{child_pointer}/items"),
                    }
                )
            elif child_type in {"string", "number", "integer", "boolean"}:
                leaves.append(child_pointer)
                field: dict[str, Any] = {
                    "type": "null" if child.get("readOnly") is True else "field",
                    "definition": child_pointer,
                }
                if child_pointer in attachment_definitions:
                    if field["type"] == "null":
                        raise SchemaFieldListError(
                            f"Attachment cannot also be read-only: {child_pointer}"
                        )
                    field["widget"] = "Attachment"
                children.append(field)
            else:
                raise SchemaFieldListError(
                    f"Unsupported schema type {child_type!r} at {child_pointer}"
                )
        return children

    ui_schema = {
        "type": "fieldList",
        "name": name,
        "label": label,
        "definition": definition,
        "children": children_for_object(schema["items"], f"{definition}/items"),
    }
    unknown_attachments = attachment_definitions - set(leaves)
    if unknown_attachments:
        raise SchemaFieldListError(
            f"Attachment definitions are not scalar leaves: {sorted(unknown_attachments)}"
        )
    return SchemaFieldListDefinition(ui_schema, tuple(leaves), tuple(arrays))
