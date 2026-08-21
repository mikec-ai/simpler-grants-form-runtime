import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form
from src.form_schema.components.person_name import (
    PersonNameComponentConfig,
    build_person_name_component,
)

_PACKAGE_DIR = Path(__file__).with_name("draft_package")
_MANIFEST_PATH = _PACKAGE_DIR / "manifest.json"


def _load_verified_artifacts() -> dict[str, Any]:
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("contract") != "simpler-draft-form-package/v1":
        raise ValueError("Unsupported R&R SF-424 draft package contract")
    if manifest.get("review_boundary", {}).get("published_coverage_eligible") is not False:
        raise ValueError("The unreviewed R&R SF-424 draft cannot be coverage eligible")

    artifacts: dict[str, Any] = {}
    for artifact_name, expected_sha256 in manifest["artifacts"].items():
        artifact_path = _PACKAGE_DIR / artifact_name
        artifact_bytes = artifact_path.read_bytes()
        actual_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError(f"R&R SF-424 draft artifact hash mismatch: {artifact_name}")
        artifacts[artifact_name] = json.loads(artifact_bytes)
    return artifacts


_WIRE_NAME_ALIASES = {
    "prefix": "PrefixName",
    "first_name": "FirstName",
    "middle_name": "MiddleName",
    "last_name": "LastName",
    "suffix": "SuffixName",
}
_WIRE_NAME_UI_ORDER = ("first_name", "last_name", "middle_name", "prefix", "suffix")
_PERSON_NAME = build_person_name_component(
    PersonNameComponentConfig(title="Person Name", description="")
)


def _compose_source_bound_person_name(
    artifacts: dict[str, Any],
    *,
    schema_path: tuple[str, ...],
    ui_base_definition: str,
    xml_path: tuple[str, ...],
) -> None:
    """Replace one resolved name with the shared component without source drift."""

    schema_node = artifacts["json-schema.json"]
    for segment in schema_path:
        schema_node = schema_node[segment]

    mounted = _PERSON_NAME.mount_wire(
        ui_base_definition,
        aliases=_WIRE_NAME_ALIASES,
        ui_order=_WIRE_NAME_UI_ORDER,
    )
    composed_schema = mounted.json_schema
    composed_schema["x-authoring"] = schema_node["x-authoring"]
    for field_name, field_schema in composed_schema["properties"].items():
        field_schema["x-authoring"] = schema_node["properties"][field_name]["x-authoring"]
    if composed_schema != schema_node:
        raise ValueError(f"R&R SF-424 person-name component drift: {ui_base_definition}")

    emitted_ui = list(mounted.ui_fields)
    resolved_ui = [
        child
        for section in artifacts["ui-schema.json"]
        for child in section["children"]
        if child.get("definition", "").startswith(f"{ui_base_definition}/properties/")
    ]
    if emitted_ui != resolved_ui:
        raise ValueError(f"R&R SF-424 person-name UI drift: {ui_base_definition}")

    xml_node = artifacts["xml-transform.json"]
    for segment in xml_path:
        xml_node = xml_node[segment]
    resolved_xml_fields = {key: value for key, value in xml_node.items() if key != "xml_transform"}
    if mounted.xml_fields != resolved_xml_fields:
        raise ValueError(f"R&R SF-424 person-name XML drift: {ui_base_definition}")

    schema_node.clear()
    schema_node.update(composed_schema)
    wrapper = xml_node["xml_transform"]
    xml_node.clear()
    xml_node["xml_transform"] = wrapper
    xml_node.update(mounted.xml_fields)


_ARTIFACTS = _load_verified_artifacts()
for _schema_path, _ui_base, _xml_path in (
    (
        ("json-schema.json", "properties", "AORInfo", "properties", "Name"),
        "/properties/AORInfo/properties/Name",
        ("xml-transform.json", "AORInfo", "Name"),
    ),
    (
        ("json-schema.json", "properties", "PDPIContactInfo", "properties", "Name"),
        "/properties/PDPIContactInfo/properties/Name",
        ("xml-transform.json", "PDPIContactInfo", "Name"),
    ),
    (
        (
            "json-schema.json",
            "properties",
            "ApplicantInfo",
            "properties",
            "ContactPersonInfo",
            "properties",
            "Name",
        ),
        "/properties/ApplicantInfo/properties/ContactPersonInfo/properties/Name",
        ("xml-transform.json", "ApplicantInfo", "ContactPersonInfo", "Name"),
    ),
):
    _compose_source_bound_person_name(
        _ARTIFACTS,
        schema_path=_schema_path[1:],
        ui_base_definition=_ui_base,
        xml_path=_xml_path[1:],
    )
FORM_JSON_SCHEMA = _ARTIFACTS["json-schema.json"]
FORM_UI_SCHEMA = _ARTIFACTS["ui-schema.json"]
FORM_RULE_SCHEMA = _ARTIFACTS["rule-schema.json"]
FORM_XML_TRANSFORM_RULES = _ARTIFACTS["xml-transform.json"]

RRSF424_v5_0 = Form(
    # Grants.gov source filename RR_SF424_5_0-V5.0_F768.xls.
    form_id=uuid.UUID("98f03cc4-5cd8-455b-a318-ba5abd0cf572"),
    legacy_form_id=768,
    form_name="[Draft] Research & Related Application for Federal Assistance (SF424 R&R)",
    short_form_name="RR_SF424_5_0",
    form_version="5.0",
    agency_code="SGG",
    form_json_schema=FORM_JSON_SCHEMA,
    form_ui_schema=FORM_UI_SCHEMA,
    form_rule_schema=FORM_RULE_SCHEMA,
    json_to_xml_schema=FORM_XML_TRANSFORM_RULES,
    form_type=FormType.RR_SF424,
    sgg_version="1.0-draft",
    is_deprecated=False,
)

del _ARTIFACTS
del _schema_path
del _ui_base
del _xml_path
