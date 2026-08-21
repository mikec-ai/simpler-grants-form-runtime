import dataclasses


@dataclasses.dataclass(frozen=True)
class ComponentDefinition:
    """Resolved, independently allocated contributions to a native form contract."""

    json_schema_properties: dict
    required: tuple[str, ...]
    ui_schema_fields: dict[str, dict]
    rule_schema: dict
    xml_transform_rules: dict
