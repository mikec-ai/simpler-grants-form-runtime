import dataclasses
from typing import Literal

from src.form_schema.components.component_definition import ComponentDefinition
from src.form_schema.shared import COMMON_SHARED_V1


@dataclasses.dataclass(frozen=True)
class OrganizationIdentityComponentConfig:
    """Exact form-level presentation deltas for organization identity questions."""

    organization_name_description: str
    sam_uei_description: str
    sam_uei_interaction: Literal["field", "null"]


def build_organization_identity_component(
    config: OrganizationIdentityComponentConfig,
) -> ComponentDefinition:
    """Build shared organization-name and SAM UEI behavior across runtime artifacts."""

    return ComponentDefinition(
        json_schema_properties={
            "organization_name": {
                "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("organization_name")}],
                "title": "Legal Name",
                "description": config.organization_name_description,
            },
            "sam_uei": {
                "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("sam_uei")}],
                "title": "SAM UEI",
                "description": config.sam_uei_description,
            },
        },
        required=("organization_name", "sam_uei"),
        ui_schema_fields={
            "organization_name": {
                "type": "field",
                "definition": "/properties/organization_name",
            },
            "sam_uei": {
                "type": config.sam_uei_interaction,
                "definition": "/properties/sam_uei",
            },
        },
        rule_schema={"sam_uei": {"gg_pre_population": {"rule": "uei"}}},
        xml_transform_rules={
            "organization_name": {"xml_transform": {"target": "OrganizationName"}},
            "sam_uei": {"xml_transform": {"target": "SAMUEI"}},
        },
    )
