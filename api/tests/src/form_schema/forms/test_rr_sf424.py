import json
from pathlib import Path

from lxml import etree as lxml_etree

from src.constants.lookup_constants import FormType
from src.form_schema.forms.rr_sf424 import RRSF424_v5_0
from src.services.xml_generation.models import XMLGenerationRequest
from src.services.xml_generation.service import XMLGenerationService

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "rr_sf424"
    / "1"
    / "0"
    / "draft_package"
)


def _resolve_schema_pointer(schema: dict, pointer: str) -> object:
    current: object = schema
    for token in pointer.removeprefix("/").split("/"):
        assert isinstance(current, dict)
        current = current[token.replace("~1", "/").replace("~0", "~")]
    return current


def test_rr_sf424_draft_is_a_complete_renderable_projection() -> None:
    assert RRSF424_v5_0.form_type == FormType.RR_SF424
    assert RRSF424_v5_0.form_version == "5.0"
    assert RRSF424_v5_0.short_form_name == "RR_SF424_5_0"
    assert RRSF424_v5_0.form_name.startswith("[Draft]")

    schema = RRSF424_v5_0.form_json_schema
    ui_schema = RRSF424_v5_0.form_ui_schema
    definitions = [child["definition"] for section in ui_schema for child in section["children"]]

    assert len(schema["properties"]) == 28
    assert len(definitions) == 107
    assert len(set(definitions)) == 107
    for definition in definitions:
        assert isinstance(_resolve_schema_pointer(schema, definition), dict)


def test_rr_sf424_draft_preserves_wire_identity_and_attachment_rules() -> None:
    xml_config = RRSF424_v5_0.json_to_xml_schema["_xml_config"]

    assert xml_config["form_name"] == "RR_SF424_5_0"
    assert xml_config["xml_structure"] == {
        "root_attributes": {"FormVersion": "5.0"},
        "root_element": "RR_SF424_5_0",
        "root_namespace_prefix": "RR_SF424_5_0",
    }
    assert set(xml_config["attachment_fields"]) == {
        "CoverLetterAttachment",
        "PreApplicationAttachment",
        "SFLLLAttachment",
    }
    assert set(RRSF424_v5_0.form_rule_schema) == {
        "CoverLetterAttachment",
        "PreApplicationAttachment",
        "SFLLLAttachment",
    }


def test_rr_sf424_draft_review_boundary_fails_closed() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    projection_report = json.loads(
        (_PACKAGE_DIR / "projection-report.json").read_text(encoding="utf-8")
    )

    assert manifest["source_evidence"]["questions"] == 107
    assert manifest["source_evidence"]["behavior_records"] == 145
    assert manifest["review_boundary"] == {
        "structural_extraction": "deterministic_from_pinned_sources",
        "semantic_mapping": "agent_proposed",
        "ui_projection": "agent_proposed",
        "policy_and_instructions": "not_reviewed",
        "published_coverage_eligible": False,
        "production_ready": False,
    }
    assert projection_report["semantic_mapping_status"] == "agent_proposed"
    assert projection_report["production_ready"] is False


def test_rr_sf424_draft_generates_namespaced_nested_xml() -> None:
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data={
                "FederalAgencyName": "National Institutes of Health",
                "ApplicantInfo": {"OrganizationInfo": {"OrganizationName": "Example University"}},
            },
            transform_config=RRSF424_v5_0.json_to_xml_schema,
        )
    )

    assert response.success is True
    assert response.xml_data is not None
    root = lxml_etree.fromstring(response.xml_data.encode("utf-8"))
    form_namespace = "http://apply.grants.gov/forms/RR_SF424_5_0-V5.0"
    global_namespace = "http://apply.grants.gov/system/GlobalLibrary-V2.0"
    assert root.tag == f"{{{form_namespace}}}RR_SF424_5_0"
    assert root.get(f"{{{form_namespace}}}FormVersion") == "5.0"
    assert (
        root.find(f"{{{form_namespace}}}FederalAgencyName").text == "National Institutes of Health"
    )
    assert (
        root.find(
            f"{{{form_namespace}}}ApplicantInfo/"
            f"{{{form_namespace}}}OrganizationInfo/"
            f"{{{global_namespace}}}OrganizationName"
        ).text
        == "Example University"
    )
