import dataclasses
from copy import deepcopy

from src.form_schema.shared import ADDRESS_SHARED_V1, COMMON_SHARED_V1


@dataclasses.dataclass(frozen=True)
class EpaApplicantIdentity:
    """Exact EPA 4700-4 applicant identity across runtime artifacts."""

    component_id: str
    contract_version: int
    json_schema_properties: dict[str, dict]
    applicant_ui_fields: tuple[dict, ...]
    uei_ui_field: dict
    rule_schema: dict
    xml_transform_rules: dict


def build_epa_applicant_identity() -> EpaApplicantIdentity:
    """Build the EPA profile without normalizing its distinct address shape."""

    properties: dict[str, dict] = {
        "applicant_name": {
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("organization_name")}],
            "title": "Name",
        },
        "applicant_address": {
            "type": "object",
            "required": ["address", "city", "state", "zip_code"],
            "properties": {
                "address": {
                    "type": "string",
                    "title": "Address",
                    "minLength": 1,
                    "maxLength": 110,
                },
                "city": {"allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("city")}]},
                "state": {"allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("state")}]},
                "zip_code": {"allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("zip_code")}]},
            },
        },
        "sam_uei": {
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("sam_uei")}],
            "title": "Unique Entity Identifier (UEI)",
        },
    }
    applicant_ui_fields = tuple(
        {"type": "field", "definition": definition}
        for definition in (
            "/properties/applicant_name",
            "/properties/applicant_address/properties/address",
            "/properties/applicant_address/properties/city",
            "/properties/applicant_address/properties/state",
            "/properties/applicant_address/properties/zip_code",
        )
    )
    xml_rules = {
        "applicant_info": {
            "xml_transform": {
                "type": "conditional",
                "target": "ApplicantInfo",
                "conditional_transform": {
                    "type": "field_grouping",
                    "source_fields": ["applicant_name", "applicant_address"],
                },
            },
            "nested_fields": {
                "applicant_name": {"xml_transform": {"target": "ApplicantName"}},
                "applicant_address": {
                    "xml_transform": {
                        "target": "ApplicantAddress",
                        "type": "nested_object",
                    },
                    "address": {"xml_transform": {"target": "Address"}},
                    "city": {"xml_transform": {"target": "City"}},
                    "state": {"xml_transform": {"target": "State"}},
                    "zip_code": {"xml_transform": {"target": "ZipCode"}},
                },
            },
        },
        "sam_uei": {"xml_transform": {"target": "SAMUEI"}},
    }
    return EpaApplicantIdentity(
        component_id="application.epa-applicant-identity",
        contract_version=1,
        json_schema_properties=deepcopy(properties),
        applicant_ui_fields=deepcopy(applicant_ui_fields),
        uei_ui_field={"type": "null", "definition": "/properties/sam_uei"},
        rule_schema={"sam_uei": {"gg_pre_population": {"rule": "uei"}}},
        xml_transform_rules=deepcopy(xml_rules),
    )
