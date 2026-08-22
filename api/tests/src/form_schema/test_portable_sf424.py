import json
from copy import deepcopy
from pathlib import Path

import jsonref

from src.form_schema.forms.sf424 import (
    FORM_JSON_SCHEMA,
    FORM_RULE_SCHEMA,
    FORM_UI_SCHEMA,
    FORM_XML_TRANSFORM_RULES,
)
from src.form_schema.portable_form_bundle import load_portable_form_bundle
from src.form_schema.shared import ADDRESS_SHARED_V1, COMMON_SHARED_V1

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPOSITORY_ROOT / "form-specs"
NATIVE_COMMON_SHARED_SCHEMA = deepcopy(COMMON_SHARED_V1.json_schema)
NATIVE_ADDRESS_SHARED_SCHEMA = deepcopy(ADDRESS_SHARED_V1.json_schema)


def _read(relative: str):
    return json.loads((BUNDLE_ROOT / relative).read_text(encoding="utf-8"))


def _normalized_resolved_schema(value, *, root: bool = False):
    if isinstance(value, list):
        return [_normalized_resolved_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: _normalized_resolved_schema(item)
        for key, item in value.items()
        if not key.startswith("x-")
        and key not in {"$schema", "$id"}
        and not (root and key == "title")
    }
    all_of = normalized.get("allOf")
    if isinstance(all_of, list) and len(all_of) == 1 and isinstance(all_of[0], dict):
        base = normalized.pop("allOf")[0]
        return {**base, **normalized}
    return normalized


def test_sf424_native_projection_dimensions_and_runtime_artifacts_are_exact() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    form = bundle.to_form("SF424")

    assert len(form.form_json_schema["properties"]) == 58
    assert form.form_ui_schema == FORM_UI_SCHEMA
    assert form.form_rule_schema == FORM_RULE_SCHEMA
    assert form.json_to_xml_schema == FORM_XML_TRANSFORM_RULES
    assert form.form_id.hex == "1623b31085be496ab84b34bdee22a68a"
    assert form.legacy_form_id == 713
    assert str(form.form_instruction_id) == "bf48a93f-d445-426f-a8fb-289bf93a2434"


def test_sf424_native_runtime_artifacts_still_match_the_portable_projection() -> None:
    form = load_portable_form_bundle(BUNDLE_ROOT).to_form("SF424")
    assert form.form_ui_schema == FORM_UI_SCHEMA
    assert form.form_rule_schema == FORM_RULE_SCHEMA
    assert form.json_to_xml_schema == FORM_XML_TRANSFORM_RULES
    assert _read("rules/sf424-v4.rules.json") == FORM_RULE_SCHEMA
    assert _read("xml/sf424-v4.xml-transform.json") == FORM_XML_TRANSFORM_RULES


def test_sf424_portable_schema_is_semantically_exact_after_reference_resolution() -> (
    None
):
    shared = {
        "https://files.simpler.grants.gov/schemas/common_shared_v1.json": (
            NATIVE_COMMON_SHARED_SCHEMA
        ),
        "https://files.simpler.grants.gov/schemas/address_shared_v1.json": (
            NATIVE_ADDRESS_SHARED_SCHEMA
        ),
    }

    def loader(uri: str, **_kwargs):
        return shared[uri.split("#", 1)[0]]

    native = jsonref.replace_refs(
        FORM_JSON_SCHEMA,
        loader=loader,
        lazy_load=False,
        proxies=False,
        jsonschema=True,
    )
    portable = load_portable_form_bundle(BUNDLE_ROOT).kernel.resolved_schema("SF424")

    assert _normalized_resolved_schema(
        portable, root=True
    ) == _normalized_resolved_schema(native, root=True)


def test_sf424_source_accounting_is_complete_but_not_published() -> None:
    ledger = _read("source-accounting/sf424-v4.source.json")
    summary = ledger["summary"]

    assert summary == {
        "countable_source_paths": 75,
        "native_json_properties": 58,
        "native_ui_sections": 24,
        "native_runtime_rules": 16,
        "native_xml_entries": 46,
        "native_xml_covered_source_paths": 57,
        "native_xml_omitted_source_paths": 18,
        "published_coverage_eligible": False,
        "accepted_mappings": 0,
        "enumerated_source_paths": 15,
        "conditional_source_paths": 9,
        "calculated_source_paths": 1,
    }
    assert len({row["path"] for row in ledger["paths"]}) == 75
    assert all(row["mapping_status"] == "agent_proposed" for row in ledger["paths"])
    assert ledger["review_boundary"] == {
        "semantic_mappings": "agent_proposed",
        "published_coverage_eligible": False,
        "production_ready": False,
        "native_parity_and_source_completeness_are_separate": True,
    }


def test_sf424_occurrence_bindings_cover_all_source_paths_and_keep_roles_distinct() -> (
    None
):
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    definition = bundle.forms_by_key["SF424"].definition
    bindings = definition["question_bindings"]
    source_paths = {
        path for binding in bindings for path in binding["context"]["source_paths"]
    }

    assert len(bindings) == 73
    assert len(source_paths) == 75
    assert all(
        binding["semantic_review"] == {"status": "agent_proposed", "events": []}
        for binding in bindings
    )
    assert definition["review_boundary"]["published_coverage_eligible"] is False

    first_name = [
        binding
        for binding in bindings
        if binding["question_id"] == "question:person:name:first"
    ]
    assert {(binding["role"], binding["form_pointer"]) for binding in first_name} == {
        ("applicant_contact", "/properties/contact_person/properties/first_name"),
        (
            "authorized_organization_representative",
            "/properties/authorized_representative/properties/first_name",
        ),
    }

    applicant_types = next(
        binding
        for binding in bindings
        if binding["form_pointer"] == "/properties/applicant_type_code"
    )
    assert applicant_types["cardinality"] == {"min": 1, "max": 3}
    assert applicant_types["context"]["source_paths"] == [
        "SF424_4_0.ApplicantTypeCode1",
        "SF424_4_0.ApplicantTypeCode2",
        "SF424_4_0.ApplicantTypeCode3",
    ]

    additional_titles = next(
        binding
        for binding in bindings
        if binding["form_pointer"] == "/properties/additional_project_title"
    )
    assert additional_titles["cardinality"] == {"min": 0, "max": 100}
    assert additional_titles["context"]["repetition"] == "repeating"


def test_sf424_source_conditions_calculation_and_enums_remain_explicit() -> None:
    ledger = _read("source-accounting/sf424-v4.source.json")
    conditional_paths = {row["path"] for row in ledger["paths"] if row["conditions"]}
    enumerated_paths = {row["path"] for row in ledger["paths"] if row["enumeration"]}
    calculations = [
        (row["path"], calculation)
        for row in ledger["paths"]
        for calculation in row["calculations"]
    ]

    assert conditional_paths == {
        "SF424_4_0.RevisionType",
        "SF424_4_0.RevisionOtherSpecify",
        "SF424_4_0.FederalAwardIdentifier",
        "SF424_4_0.Applicant.State",
        "SF424_4_0.Applicant.Province",
        "SF424_4_0.Applicant.ZipPostalCode",
        "SF424_4_0.ApplicantTypeOtherSpecify",
        "SF424_4_0.StateReviewAvailableDate",
        "SF424_4_0.DebtExplanation",
    }
    assert len(enumerated_paths) == 15
    assert calculations == [
        (
            "SF424_4_0.TotalEstimatedFunding",
            {
                "dependency_resolution": "runtime_path_resolution_required",
                "operand_hints": [],
                "operator": "sum_references",
            },
        )
    ]
    assert FORM_RULE_SCHEMA["total_estimated_funding"]["gg_pre_population"] == {
        "rule": "sum_monetary",
        "fields": [
            "federal_estimated_funding",
            "applicant_estimated_funding",
            "state_estimated_funding",
            "local_estimated_funding",
            "other_estimated_funding",
            "program_income_estimated_funding",
        ],
    }


def test_sf424_native_xml_omissions_are_visible_and_fail_closed() -> None:
    ledger = _read("source-accounting/sf424-v4.source.json")
    assert set(ledger["native_xml_omissions"]) == {
        "SF424_4_0.ApplicantID",
        "SF424_4_0.AuthorizedRepresentative.MiddleName",
        "SF424_4_0.AuthorizedRepresentative.PrefixName",
        "SF424_4_0.AuthorizedRepresentative.SuffixName",
        "SF424_4_0.AuthorizedRepresentativeFax",
        "SF424_4_0.ContactPerson.MiddleName",
        "SF424_4_0.ContactPerson.PrefixName",
        "SF424_4_0.ContactPerson.SuffixName",
        "SF424_4_0.DepartmentName",
        "SF424_4_0.DivisionName",
        "SF424_4_0.FederalAwardIdentifier",
        "SF424_4_0.FederalEntityIdentifier",
        "SF424_4_0.OrganizationAffiliation",
        "SF424_4_0.RevisionOtherSpecify",
        "SF424_4_0.RevisionType",
        "SF424_4_0.StateApplicationID",
        "SF424_4_0.StateReceiveDate",
        "SF424_4_0.Title",
    }
    assert FORM_XML_TRANSFORM_RULES["fax_number"]["xml_transform"]["target"] == "Fax"
    assert "fax" not in FORM_XML_TRANSFORM_RULES


def test_sf424_static_content_is_pdf_bound_without_claiming_acceptance() -> None:
    static = _read("static/sf424-v4.static.json")

    assert static["source"] == {
        "title": "Application for Federal Assistance (SF-424)",
        "url": "https://apply07.grants.gov/apply/forms/readonly/SF424_4_0-V4.0.pdf",
        "sha256": "ad3d5f4bc3f6239fdaf9b7daf13a44761af541bb388b89ce0d1946ee5002e2d2",
    }
    assert [item["content_id"] for item in static["items"]] == [
        "sf424:certification:21",
        "sf424:certification-reference:21",
    ]


def test_sf424_portable_and_native_constraint_differences_are_not_hidden() -> None:
    source_rows = {
        row["path"]: row
        for row in _read("source-accounting/sf424-v4.source.json")["paths"]
    }

    assert FORM_JSON_SCHEMA["properties"]["division_name"]["maxLength"] == 100
    assert source_rows["SF424_4_0.DivisionName"]["constraints"]["maxLength"] == 30
    assert "maxLength" not in FORM_JSON_SCHEMA["properties"]["revision_other_specify"]
    assert (
        source_rows["SF424_4_0.RevisionOtherSpecify"]["constraints"]["maxLength"] == 21
    )
    assert FORM_JSON_SCHEMA["properties"]["federal_estimated_funding"] == {
        "allOf": [
            {
                "$ref": (
                    "https://files.simpler.grants.gov/schemas/"
                    "common_shared_v1.json#/budget_monetary_amount"
                )
            }
        ],
        "title": "Federal Estimated Funding",
        "description": "Enter the dollar amount.",
    }
    assert (
        source_rows["SF424_4_0.FederalEstimatedFunding"]["constraints"]["minInclusive"]
        == "0.00"
    )
