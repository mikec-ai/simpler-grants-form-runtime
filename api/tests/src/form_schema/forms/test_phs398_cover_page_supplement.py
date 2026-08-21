import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from lxml import etree as lxml_etree

from src.constants.lookup_constants import FormType
from src.form_schema.components.person_name import (
    PersonNameComponentConfig,
    build_person_name_component,
)
from src.form_schema.forms.phs398_cover_page_supplement import (
    PHS398CoverPageSupplement_v5_0,
    _form_json,
)
from src.services.xml_generation.models import XMLGenerationRequest
from src.services.xml_generation.service import XMLGenerationService

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "phs398_cover_page_supplement"
    / "1"
    / "0"
    / "draft_package"
)


def _walk_ui(nodes: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for node in nodes:
        yield node
        if node["type"] in {"section", "fieldList"}:
            yield from _walk_ui(node["children"])


def _ui_by_definition() -> dict[str, dict[str, Any]]:
    return {
        node["definition"]: node
        for node in _walk_ui(PHS398CoverPageSupplement_v5_0.form_ui_schema)
        if isinstance(node.get("definition"), str)
    }


def _minimal_data() -> dict[str, Any]:
    return {
        "ProgramIncome": "N: No",
        "StemCells": {"isHumanStemCellsInvolved": "N: No"},
        "isHumanFetalTissueInvolved": "N: No",
    }


def test_cover_page_supplement_is_a_complete_source_accounted_canary() -> None:
    form = PHS398CoverPageSupplement_v5_0
    assert form.form_type == FormType.PHS398_COVER_PAGE_SUPPLEMENT
    assert form.form_version == "5.0"
    assert form.short_form_name == "PHS398_CoverPageSupplement_5_0"
    assert form.form_name.startswith("[Draft]")
    assert form.json_to_xml_schema is not None
    assert len(_form_json._BUILD.condition_rule_ids) == 22
    assert len(_form_json._BUILD.calculation_rule_ids) == 0
    assert len(_form_json._BUILD.attachment_paths) == 2


def test_yes_no_values_and_conditions_use_exact_xsd_wire_values() -> None:
    schema = PHS398CoverPageSupplement_v5_0.form_json_schema
    assert schema["properties"]["ProgramIncome"]["enum"] == ["Y: Yes", "N: No"]
    fields = _ui_by_definition()
    income = fields["/properties/IncomeBudgetPeriod/items/properties/AnticipatedAmount"]
    assert income["conditional"]["when"] == {
        "op": "equals",
        "ref": {"scope": "root", "pointer": "/ProgramIncome"},
        "value": "Y: Yes",
    }
    euthanasia = fields["/properties/VertebrateAnimals/properties/AVMAConsistentIndicator"]
    assert euthanasia["conditional"]["when"]["value"] == "Y: Yes"


def test_repeated_and_attachment_shapes_use_native_runtime_contracts() -> None:
    schema = PHS398CoverPageSupplement_v5_0.form_json_schema
    income = schema["properties"]["IncomeBudgetPeriod"]
    assert income["type"] == "array"
    assert income["maxItems"] == 10
    assert set(income["items"]["required"]) == {
        "BudgetPeriod",
        "AnticipatedAmount",
        "Source",
    }
    cell_lines = schema["properties"]["StemCells"]["properties"]["CellLines"]
    assert cell_lines["type"] == "array"
    assert cell_lines["maxItems"] == 200
    fields = _ui_by_definition()
    assert fields["/properties/StemCells/properties/CellLines"]["type"] == "null"
    assert fields["/properties/ComplianceAssurance/properties/attFile"]["widget"] == ("Attachment")


def test_pdf_presentation_uses_the_six_official_sections_and_field_order() -> None:
    sections = PHS398CoverPageSupplement_v5_0.form_ui_schema
    assert [section["label"] for section in sections] == [
        "1. Vertebrate Animals Section",
        "2. Program Income Section",
        "3. Human Embryonic Stem Cells Section",
        "4. Human Fetal Tissue Section",
        "5. Inventions and Patents Section (for Renewal applications)",
        "6. Change of Investigator/Change of Recipient Organization Section",
    ]
    assert [child["definition"] for child in sections[0]["children"]] == [
        "/properties/VertebrateAnimals/properties/AnimalEuthanasiaIndicator",
        "/properties/VertebrateAnimals/properties/AVMAConsistentIndicator",
        "/properties/VertebrateAnimals/properties/EuthanasiaMethodDescription",
    ]
    assert [child["definition"] for child in sections[5]["children"]] == [
        "/properties/IsChangeOfPDPI",
        "/properties/FormerPD_Name/properties/PrefixName",
        "/properties/FormerPD_Name/properties/FirstName",
        "/properties/FormerPD_Name/properties/MiddleName",
        "/properties/FormerPD_Name/properties/LastName",
        "/properties/FormerPD_Name/properties/SuffixName",
        "/properties/IsChangeOfInstitution",
        "/properties/FormerInstitutionName",
    ]
    program_income_list = sections[1]["children"][1]
    assert program_income_list["type"] == "fieldList"
    assert program_income_list["conditional"] == program_income_list["children"][0]["conditional"]


def test_former_pd_name_reuses_the_shared_person_name_constraints() -> None:
    source_name = PHS398CoverPageSupplement_v5_0.form_json_schema["properties"]["FormerPD_Name"]
    mounted = build_person_name_component(
        PersonNameComponentConfig(title="Former PD/PI", description="")
    ).mount_wire(
        "/properties/FormerPD_Name",
        aliases={
            "prefix": "PrefixName",
            "first_name": "FirstName",
            "middle_name": "MiddleName",
            "last_name": "LastName",
            "suffix": "SuffixName",
        },
        ui_order=("first_name", "last_name", "middle_name", "prefix", "suffix"),
    )
    assert source_name["required"] == mounted.json_schema["required"]
    for field_name, shared_field in mounted.json_schema["properties"].items():
        source_field = source_name["properties"][field_name]
        for constraint in ("type", "minLength", "maxLength"):
            assert source_field.get(constraint) == shared_field.get(constraint)


def test_machine_readable_metadata_does_not_count_attachments_as_questions() -> None:
    metadata = PHS398CoverPageSupplement_v5_0.form_json_schema["x-simpler-field-metadata"]
    assert metadata["counts"] == {
        "applicant_question": 21,
        "calculated_output": 0,
        "technical_field": 15,
        "static_content": 0,
        "attachment": 2,
        "total_records": 38,
    }
    compliance = next(
        record
        for record in metadata["records"]
        if record["runtime_data_pointer_template"] == "/ComplianceAssurance/attFile"
    )
    assert compliance["classification"] == "attachment"
    assert compliance["counts_as_applicant_question"] is False
    assert compliance["canonical_semantic_question_id"] == (
        "concept:attachment:fetal-tissue-compliance-assurance"
    )
    assert compliance["published_coverage_eligible"] is False


def test_minimal_response_is_schema_valid() -> None:
    assert (
        list(
            Draft202012Validator(PHS398CoverPageSupplement_v5_0.form_json_schema).iter_errors(
                _minimal_data()
            )
        )
        == []
    )


def test_source_pinned_xml_is_valid_offline_and_omits_optional_attachments() -> None:
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data=_minimal_data(),
            transform_config=PHS398CoverPageSupplement_v5_0.json_to_xml_schema,
        )
    )
    assert response.success is True
    assert "ComplianceAssurance" not in response.xml_data
    assert "HFTIRBConsentForm" not in response.xml_data

    xsd_root = _PACKAGE_DIR / "work" / "grantsgov-xsds"

    class OfflineResolver(lxml_etree.Resolver):
        def resolve(self, url, public_id, context):
            local_path = xsd_root / "dependencies" / Path(url).name
            if local_path.exists():
                return self.resolve_filename(str(local_path), context)
            return None

    parser = lxml_etree.XMLParser(no_network=True)
    parser.resolvers.add(OfflineResolver())
    schema_document = lxml_etree.parse(
        str(xsd_root / "PHS398_CoverPageSupplement_5_0-V5.0.xsd"), parser
    )
    schema = lxml_etree.XMLSchema(schema_document)
    schema.assertValid(lxml_etree.fromstring(response.xml_data.encode()))


def test_package_hashes_and_review_gates_are_explicit() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash
    assert manifest["source_evidence"]["nodes"] == 38
    assert manifest["source_evidence"]["resolved_runtime_rules"] == 22
    presentation_path = _PACKAGE_DIR / "presentation-evidence.json"
    assert hashlib.sha256(presentation_path.read_bytes()).hexdigest() == (
        manifest["source_evidence"]["official_pdf"]["presentation_evidence_sha256"]
    )
    presentation = json.loads(presentation_path.read_text(encoding="utf-8"))
    assert presentation["source"]["sha256"] == (
        "82f9827f440018a0d3cfee25ec9f9696063143a5c618fb2dafe778ac80f183e8"
    )
    assert [section["ordinal"] for section in presentation["sections"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]
    assert manifest["open_gates"] == {
        "xml_projection": "source_pinned_plan_compiled_to_native_runtime",
        "scalar_string_arrays": ["PHS398_CoverPageSupplement_5_0.StemCells.CellLines"],
        "pdf_visual_review": "agent_complete_coverage_ineligible",
        "cross_form_conditions": [
            "Inventions and Patents section applicability depends on Renewal application context"
        ],
        "policy_and_accessibility_review": "not_complete",
        "human_acceptance": "not_complete",
    }
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False
