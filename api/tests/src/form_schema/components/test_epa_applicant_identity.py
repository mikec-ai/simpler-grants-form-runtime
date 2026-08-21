from src.form_schema.components.epa_applicant_identity import build_epa_applicant_identity


def test_epa_applicant_identity_preserves_its_distinct_address_profile() -> None:
    identity = build_epa_applicant_identity()

    assert identity.component_id == "application.epa-applicant-identity"
    assert tuple(identity.json_schema_properties) == (
        "applicant_name",
        "applicant_address",
        "sam_uei",
    )
    address = identity.json_schema_properties["applicant_address"]
    assert address["required"] == ["address", "city", "state", "zip_code"]
    assert tuple(address["properties"]) == ("address", "city", "state", "zip_code")
    assert identity.rule_schema == {"sam_uei": {"gg_pre_population": {"rule": "uei"}}}
    assert identity.xml_transform_rules["applicant_info"]["xml_transform"]["conditional_transform"][
        "source_fields"
    ] == ["applicant_name", "applicant_address"]


def test_epa_applicant_identity_allocates_independent_artifacts() -> None:
    first = build_epa_applicant_identity()
    second = build_epa_applicant_identity()
    first.json_schema_properties["applicant_name"]["title"] = "mutated"
    assert second.json_schema_properties["applicant_name"]["title"] == "Name"
