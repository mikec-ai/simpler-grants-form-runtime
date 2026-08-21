import dataclasses
import re
from copy import deepcopy

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.shared import ADDRESS_SHARED_V1, COMMON_SHARED_V1

_SCHEMA_POINTER = re.compile(
    r"^/properties/[a-z][a-z0-9_]*(?:/(?:properties/[a-z][a-z0-9_]*|items))*$"
)
_CONGRESSIONAL_DISTRICT_PATTERN = r"^[A-Z0-9]{2}-[A-Za-z0-9]{3}$"
_FIELD_ORDER = (
    "submitting_as_individual",
    "organization_name",
    "uei",
    "address/street1",
    "address/street2",
    "address/city",
    "address/county",
    "address/state",
    "address/province",
    "address/country",
    "address/zip_code",
    "congressional_district",
)


@dataclasses.dataclass(frozen=True)
class PerformanceSiteLocation:
    component_id: str
    contract_version: int
    json_schema: dict
    ui_fields: tuple[dict, ...]
    xml_fields: dict


def _site_properties() -> dict:
    return {
        "submitting_as_individual": {
            "type": "boolean",
            "title": "I am submitting an application as an individual, and not on behalf of a company, state, local or tribal government, academia, or other type of organization.",
            "description": "Select if submitting application as an individual and not on behalf of or representing any organization.",
        },
        "organization_name": {
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("organization_name")}],
            "title": "Organization Name",
            "description": "Indicate the organization name of the site where the work will be performed.",
        },
        "uei": {
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("sam_uei")}],
            "title": "UEI",
            "description": "Enter the UEI associated with the organization where the project will be performed.",
        },
        "address": {
            "allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("address")}],
            "title": "Address",
            "description": "Enter the performance site address.",
        },
        "congressional_district": {
            "type": "string",
            "title": "Project/Performance Site Congressional District",
            "description": (
                "Enter the Congressional District in the format: 2 character State "
                "Abbreviation - 3 character District Number. Examples: CA-005, MD-all, "
                "US-all, 00-000. Required if the site is in the United States."
            ),
            "minLength": 6,
            "maxLength": 6,
            "pattern": _CONGRESSIONAL_DISTRICT_PATTERN,
        },
    }


def _us_congressional_district_condition() -> dict:
    return {
        "if": {
            "properties": {
                "address": {
                    "properties": {"country": {"const": "USA: UNITED STATES"}},
                    "required": ["country"],
                }
            },
            "required": ["address"],
        },
        "then": {"required": ["congressional_district"]},
    }


def _xml_fields() -> dict:
    address_fields = {
        "street1": "Street1",
        "street2": "Street2",
        "city": "City",
        "county": "County",
        "state": "State",
        "province": "Province",
        "zip_code": "ZipPostalCode",
        "country": "Country",
    }
    return {
        "submitting_as_individual": {
            "xml_transform": {
                "target": "Individual",
                "value_transform": {"type": "boolean_to_yes_no"},
            }
        },
        "organization_name": {"xml_transform": {"target": "OrganizationName"}},
        "uei": {"xml_transform": {"target": "SAMUEI"}},
        "address": {
            "xml_transform": {"target": "Address", "type": "nested_object"},
            **{
                field: {"xml_transform": {"target": target, "namespace": "globLib"}}
                for field, target in address_fields.items()
            },
        },
        "congressional_district": {
            "xml_transform": {"target": "CongressionalDistrictProgramProject"}
        },
    }


def build_performance_site_location(
    base_definition: str, *, require_organization_unless_individual: bool
) -> PerformanceSiteLocation:
    """Build one exact performance-site profile at a fixed or repeated UI path."""

    if not isinstance(base_definition, str) or not _SCHEMA_POINTER.fullmatch(base_definition):
        raise ComponentDefinitionError("performance site requires a schema property pointer")
    if not isinstance(require_organization_unless_individual, bool):
        raise ComponentDefinitionError("organization requirement must be boolean")

    conditions = [_us_congressional_district_condition()]
    if require_organization_unless_individual:
        conditions.append(
            {
                "if": {
                    "properties": {"submitting_as_individual": {"const": True}},
                    "required": ["submitting_as_individual"],
                },
                "else": {"required": ["organization_name"]},
            }
        )
    schema = {
        "type": "object",
        "required": ["address"],
        "allOf": conditions,
        "properties": _site_properties(),
    }
    ui_fields = tuple(
        {
            "type": "field",
            "definition": f"{base_definition}/properties/{path.replace('/', '/properties/')}",
        }
        for path in _FIELD_ORDER
    )
    return PerformanceSiteLocation(
        component_id="application.performance-site-location",
        contract_version=1,
        json_schema=deepcopy(schema),
        ui_fields=deepcopy(ui_fields),
        xml_fields=_xml_fields(),
    )
