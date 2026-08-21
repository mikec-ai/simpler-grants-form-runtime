import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
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
    assert len(definitions) == 106
    assert len(set(definitions)) == 106
    for definition in definitions:
        assert isinstance(_resolve_schema_pointer(schema, definition), dict)


def test_shared_person_name_composition_preserves_resolved_artifacts() -> None:
    baseline_schema = json.loads((_PACKAGE_DIR / "json-schema.json").read_text(encoding="utf-8"))
    baseline_ui = json.loads((_PACKAGE_DIR / "ui-schema.json").read_text(encoding="utf-8"))
    assert RRSF424_v5_0.json_to_xml_schema == json.loads(
        (_PACKAGE_DIR / "xml-transform.json").read_text(encoding="utf-8")
    )

    expected_name_paths = {
        "/properties/AORInfo/properties/Name",
        "/properties/PDPIContactInfo/properties/Name",
        "/properties/ApplicantInfo/properties/ContactPersonInfo/properties/Name",
    }
    for name_path in expected_name_paths:
        assert _resolve_schema_pointer(
            RRSF424_v5_0.form_json_schema, name_path
        ) == _resolve_schema_pointer(baseline_schema, name_path)
        runtime_name_fields = [
            child
            for section in RRSF424_v5_0.form_ui_schema
            for child in section["children"]
            if child.get("definition", "").startswith(f"{name_path}/properties/")
        ]
        baseline_name_fields = [
            child
            for section in baseline_ui
            for child in section["children"]
            if child.get("definition", "").startswith(f"{name_path}/properties/")
        ]
        assert runtime_name_fields == baseline_name_fields
    resolved_name_paths = {
        definition.rsplit("/properties/", 1)[0]
        for section in RRSF424_v5_0.form_ui_schema
        for child in section["children"]
        if (definition := child.get("definition", ""))
        and definition.endswith(
            (
                "/PrefixName",
                "/FirstName",
                "/MiddleName",
                "/LastName",
                "/SuffixName",
            )
        )
    }
    assert resolved_name_paths == expected_name_paths

    global_library_ref = "https://apply07.grants.gov/apply/system/schemas/GlobalLibrary-V2.0.xsd"
    for name_path in expected_name_paths:
        name_schema = _resolve_schema_pointer(RRSF424_v5_0.form_json_schema, name_path)
        assert isinstance(name_schema, dict)
        assert len(name_schema["properties"]) == 5
        for field_schema in name_schema["properties"].values():
            authoring = field_schema["x-authoring"]
            assert authoring["published_coverage_eligible"] is False
            assert any(global_library_ref in item for item in authoring["provenance"])


def test_country_aware_address_component_preserves_structure_and_wire_mapping() -> None:
    baseline_schema = json.loads((_PACKAGE_DIR / "json-schema.json").read_text(encoding="utf-8"))
    baseline_ui = json.loads((_PACKAGE_DIR / "ui-schema.json").read_text(encoding="utf-8"))
    address_paths = (
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/Address",
        "/properties/ApplicantInfo/properties/ContactPersonInfo/properties/Address",
        "/properties/PDPIContactInfo/properties/Address",
        "/properties/AORInfo/properties/Address",
    )

    for address_path in address_paths:
        runtime_address = _resolve_schema_pointer(RRSF424_v5_0.form_json_schema, address_path)
        assert isinstance(runtime_address, dict)
        structural_address = dict(runtime_address)
        structural_address.pop("allOf")
        assert structural_address == _resolve_schema_pointer(baseline_schema, address_path)

        runtime_fields = [
            child
            for section in RRSF424_v5_0.form_ui_schema
            for child in section["children"]
            if child.get("definition", "").startswith(f"{address_path}/properties/")
        ]
        baseline_fields = [
            child
            for section in baseline_ui
            for child in section["children"]
            if child.get("definition", "").startswith(f"{address_path}/properties/")
        ]
        assert [
            {key: value for key, value in field.items() if key != "conditional"}
            for field in runtime_fields
        ] == baseline_fields
        assert len([field for field in runtime_fields if "conditional" in field]) == 3


def test_all_four_addresses_execute_us_and_non_us_rules() -> None:
    address_paths = (
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/Address",
        "/properties/ApplicantInfo/properties/ContactPersonInfo/properties/Address",
        "/properties/PDPIContactInfo/properties/Address",
        "/properties/AORInfo/properties/Address",
    )
    for address_path in address_paths:
        address_schema = _resolve_schema_pointer(RRSF424_v5_0.form_json_schema, address_path)
        validator = Draft202012Validator(address_schema)
        us_errors = list(
            validator.iter_errors(
                {
                    "Country": "USA: UNITED STATES",
                    "City": "Washington",
                    "Street1": "1 Main St",
                    "ZipPostalCode": "12345",
                }
            )
        )
        assert any("State" in error.message for error in us_errors)
        assert any(error.validator == "minLength" for error in us_errors)
        assert not list(
            validator.iter_errors(
                {
                    "Country": "CAN: CANADA",
                    "City": "Ottawa",
                    "Street1": "1 Main St",
                }
            )
        )


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
    assert {
        "CoverLetterAttachment",
        "PreApplicationAttachment",
        "SFLLLAttachment",
    } < set(RRSF424_v5_0.form_rule_schema)


def test_rr_sf424_source_conditions_are_live_validation_rules() -> None:
    validator = Draft202012Validator(RRSF424_v5_0.form_json_schema)

    cases = [
        (
            {"ApplicationType": {"ApplicationTypeCode": "Renewal"}},
            "FederalID",
        ),
        (
            {"SubmissionTypeCode": "Change/Corrected Application"},
            "GGTrackingID",
        ),
        (
            {"ApplicantType": {"ApplicantTypeCode": "X: Other (specify)"}},
            "ApplicantTypeCodeOtherExplanation",
        ),
        (
            {"ApplicationType": {"isOtherAgencySubmission": "Y: Yes"}},
            "OtherAgencySubmissionExplanation",
        ),
        (
            {"StateReview": {"StateReviewCodeType": "Y: Yes"}},
            "StateReviewDate",
        ),
        (
            {"ApplicationType": {"ApplicationTypeCode": "Revision"}},
            "RevisionCode",
        ),
        (
            {
                "ApplicationType": {
                    "ApplicationTypeCode": "Revision",
                    "RevisionCode": "E",
                }
            },
            "RevisionCodeOtherExplanation",
        ),
    ]
    for instance, expected_missing_field in cases:
        messages = [error.message for error in validator.iter_errors(instance)]
        assert any(expected_missing_field in message for message in messages)

    trust_errors = [error.message for error in validator.iter_errors({"TrustAgree": "N: No"})]
    assert any("Y: Yes" in message for message in trust_errors)


def test_rr_sf424_source_conditions_control_ui_and_lifecycle_fields() -> None:
    ui_by_definition = {
        child["definition"]: child
        for section in RRSF424_v5_0.form_ui_schema
        for child in section["children"]
    }
    assert "conditional" not in ui_by_definition["/properties/FederalID"]
    assert ui_by_definition["/properties/GGTrackingID"]["conditional"]["when"] == {
        "op": "equals",
        "ref": {"scope": "root", "pointer": "/SubmissionTypeCode"},
        "value": "Change/Corrected Application",
    }
    revision_definition = "/properties/ApplicationType/properties/RevisionCode"
    revision_other_definition = (
        "/properties/ApplicationType/properties/RevisionCodeOtherExplanation"
    )
    assert ui_by_definition[revision_definition] == {
        "type": "field",
        "definition": revision_definition,
        "widget": "EncodedCheckboxGroup",
        "conditional": {
            "when": {
                "op": "equals",
                "ref": {
                    "scope": "root",
                    "pointer": "/ApplicationType/ApplicationTypeCode",
                },
                "value": "Revision",
            },
            "then": {"visible": True},
            "otherwise": {"visible": False},
        },
    }
    assert ui_by_definition[revision_other_definition]["conditional"]["when"] == {
        "op": "all",
        "predicates": [
            {
                "op": "equals",
                "ref": {
                    "scope": "root",
                    "pointer": "/ApplicationType/ApplicationTypeCode",
                },
                "value": "Revision",
            },
            {
                "op": "equals",
                "ref": {"scope": "root", "pointer": "/ApplicationType/RevisionCode"},
                "value": "E",
            },
        ],
    }
    for definition in (
        "/properties/FederalAgencyName",
        "/properties/CFDANumber",
        "/properties/ActivityTitle",
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/SAMUEI",
        "/properties/AOR_Signature",
        "/properties/AOR_SignedDate",
    ):
        assert ui_by_definition[definition]["type"] == "null"

    rules = RRSF424_v5_0.form_rule_schema
    assert rules["FederalAgencyName"] == {"gg_pre_population": {"rule": "agency_name"}}
    assert rules["ApplicantInfo"]["OrganizationInfo"]["SAMUEI"] == {
        "gg_pre_population": {"rule": "uei"}
    }
    assert rules["AOR_Signature"] == {"gg_post_population": {"rule": "signature"}}
    assert rules["AOR_SignedDate"] == {"gg_post_population": {"rule": "current_date"}}
    country_default = {
        "gg_pre_population": {
            "rule": "default_value",
            "value": "USA: UNITED STATES",
        }
    }
    assert rules["ApplicantInfo"]["OrganizationInfo"]["Address"]["Country"] == country_default
    assert rules["ApplicantInfo"]["ContactPersonInfo"]["Address"]["Country"] == country_default
    assert rules["ApplicationType"]["RevisionCode"] == {
        "gg_pre_population": {
            "rule": "clear_unless_all_equal",
            "conditions": [{"field": "ApplicationType.ApplicationTypeCode", "value": "Revision"}],
            "order": 1,
        }
    }
    assert rules["ApplicationType"]["RevisionCodeOtherExplanation"] == {
        "gg_pre_population": {
            "rule": "clear_unless_all_equal",
            "conditions": [
                {"field": "ApplicationType.ApplicationTypeCode", "value": "Revision"},
                {"field": "ApplicationType.RevisionCode", "value": "E"},
            ],
            "order": 2,
        }
    }

    revision_schema = RRSF424_v5_0.form_json_schema["properties"]["ApplicationType"]["properties"][
        "RevisionCode"
    ]
    assert revision_schema["enum"] == ["A", "B", "C", "D", "E", "AC", "AD", "BC", "BD"]
    assert revision_schema["x-encoded-checkbox-group"]["combinations"] == [
        {"value": value, "members": list(value)} for value in revision_schema["enum"]
    ]

    sam_uei = RRSF424_v5_0.form_json_schema["properties"]["ApplicantInfo"]["properties"][
        "OrganizationInfo"
    ]["properties"]["SAMUEI"]
    assert {key: sam_uei[key] for key in ("minLength", "maxLength")} == {
        "minLength": 12,
        "maxLength": 12,
    }
    assert "pattern" not in sam_uei
    assert (
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/EIN"
        not in ui_by_definition
    )
    assert "AOR_Signature" not in RRSF424_v5_0.form_json_schema["required"]
    assert "AOR_SignedDate" not in RRSF424_v5_0.form_json_schema["required"]
    for pointer in (
        "/properties/ApplicantInfo/properties/ContactPersonInfo/properties/Email",
        "/properties/PDPIContactInfo/properties/Email",
        "/properties/AORInfo/properties/Email",
    ):
        assert _resolve_schema_pointer(RRSF424_v5_0.form_json_schema, pointer)["format"] == "email"


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
    address_bindings = [
        binding
        for binding in manifest["component_bindings"]
        if binding["component_id"] == "people.country-aware-address.global-library-v2"
    ]
    assert len(address_bindings) == 4
    assert {binding["binding_status"] for binding in address_bindings} == {
        "exact_source_bound_structure"
    }
    assert manifest["source_review"] == {
        "instructions_pdf_sha256": (
            "666647fdeb7d9d69f2d36dedc74f09ff6a9540776f87c5a5c5b0593219736bd1"
        ),
        "readonly_pdf_sha256": ("592a1faf1cfdac3e350a22c6fbae3b8c6f229b6c7de29ec18273b60c9235dd6b"),
        "xfa_sample_sha256": ("06dd92da28b4afb8190fd0edaeb7a0dac3ae2d601adcc1ab9a5e0fc93c09f523"),
        "review_status": "agent_full_source_review",
        "published_coverage_eligible": False,
        "open_behavior_queue": True,
        "open_source_conflicts": True,
    }
    behavior_slice = manifest["executed_behavior_slice"]
    assert behavior_slice["review_status"] == "agent_full_source_review"
    assert behavior_slice["published_coverage_eligible"] is False
    assert set(behavior_slice["conditional_required_paths"]) == {
        "RR_SF424_5_0.FederalID",
        "RR_SF424_5_0.GGTrackingID",
        "RR_SF424_5_0.ApplicationType.OtherAgencySubmissionExplanation",
        "RR_SF424_5_0.ApplicantType.ApplicantTypeCodeOtherExplanation",
        "RR_SF424_5_0.StateReview.StateReviewDate",
        "RR_SF424_5_0.ApplicantInfo.OrganizationInfo.Address.State",
        "RR_SF424_5_0.ApplicantInfo.OrganizationInfo.Address.ZipPostalCode",
        "RR_SF424_5_0.ApplicantInfo.ContactPersonInfo.Address.State",
        "RR_SF424_5_0.ApplicantInfo.ContactPersonInfo.Address.ZipPostalCode",
        "RR_SF424_5_0.PDPIContactInfo.Address.State",
        "RR_SF424_5_0.PDPIContactInfo.Address.ZipPostalCode",
        "RR_SF424_5_0.AORInfo.Address.State",
        "RR_SF424_5_0.AORInfo.Address.ZipPostalCode",
        "RR_SF424_5_0.ApplicationType.RevisionCode",
        "RR_SF424_5_0.ApplicationType.RevisionCodeOtherExplanation",
    }
    assert set(behavior_slice["population_paths"]) == {
        "RR_SF424_5_0.FederalAgencyName",
        "RR_SF424_5_0.CFDANumber",
        "RR_SF424_5_0.ActivityTitle",
        "RR_SF424_5_0.ApplicantInfo.OrganizationInfo.SAMUEI",
        "RR_SF424_5_0.AOR_Signature",
        "RR_SF424_5_0.AOR_SignedDate",
        "RR_SF424_5_0.ApplicantInfo.OrganizationInfo.Address.Country",
        "RR_SF424_5_0.ApplicantInfo.ContactPersonInfo.Address.Country",
    }
    assert behavior_slice["encoded_checkbox_paths"] == ["RR_SF424_5_0.ApplicationType.RevisionCode"]
    assert set(behavior_slice["stale_clear_paths"]) == {
        "RR_SF424_5_0.ApplicationType.RevisionCode",
        "RR_SF424_5_0.ApplicationType.RevisionCodeOtherExplanation",
    }
    assert set(behavior_slice["validation_paths"]) == {
        "RR_SF424_5_0.TrustAgree",
        "RR_SF424_5_0.ApplicantInfo.OrganizationInfo.SAMUEI",
        "RR_SF424_5_0.ApplicantInfo.ContactPersonInfo.Email",
        "RR_SF424_5_0.PDPIContactInfo.Email",
        "RR_SF424_5_0.AORInfo.Email",
    }
    evidence_path = _PACKAGE_DIR / behavior_slice["evidence_file"]
    assert (
        hashlib.sha256(evidence_path.read_bytes()).hexdigest() == behavior_slice["evidence_sha256"]
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["published_coverage_eligible"] is False
    assert len(evidence["records"]) == 39
    assert len({record["evidence_id"] for record in evidence["records"]}) == 39
    assert all(
        record["source_artifact"] in evidence["source_artifacts"] for record in evidence["records"]
    )
    assert {
        record["target_path"]
        for record in evidence["records"]
        if "conditional_required" in record["effects"]
    } == set(behavior_slice["conditional_required_paths"])
    assert {
        record["target_path"]
        for record in evidence["records"]
        if "conditional_presentation" in record["effects"]
    } == set(behavior_slice["conditional_presentation_paths"])
    assert {
        record["target_path"]
        for record in evidence["records"]
        if "default_usa_if_missing" in record["effects"]
    } <= set(behavior_slice["population_paths"])
    review_note = (_PACKAGE_DIR / "source-review.md").read_text(encoding="utf-8")
    assert "executed only\nthe three attachment-type checks" in review_note
    assert "Do not add a 15c funding calculation" in review_note


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
