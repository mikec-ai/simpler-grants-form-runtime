from src.form_schema.components.assurances_signature import (
    AssurancesSignatureComponentConfig,
    build_assurances_signature_component,
)


def test_assurances_signature_exposes_only_the_exact_shared_profile_delta() -> None:
    lower = build_assurances_signature_component(
        AssurancesSignatureComponentConfig(date_title="Date submitted")
    ).mount_root()
    upper = build_assurances_signature_component(
        AssurancesSignatureComponentConfig(date_title="Date Submitted")
    ).mount_root()

    assert lower.component_id == "application.assurances-signature"
    assert tuple(lower.json_schema_properties) == (
        "signature",
        "title",
        "applicant_organization",
        "date_signed",
    )
    assert lower.json_schema_properties["date_signed"]["title"] == "Date submitted"
    assert upper.json_schema_properties["date_signed"]["title"] == "Date Submitted"
    assert {
        key: value for key, value in lower.json_schema_properties.items() if key != "date_signed"
    } == {key: value for key, value in upper.json_schema_properties.items() if key != "date_signed"}
    assert lower.rule_schema == {}
    assert lower.xml_transform_rules == {}


def test_assurances_signature_allocates_independent_outputs() -> None:
    definition = build_assurances_signature_component(
        AssurancesSignatureComponentConfig(date_title="Date submitted")
    )
    first = definition.mount_root()
    second = definition.mount_root()
    first.json_schema_properties["signature"]["title"] = "mutated"
    assert second.json_schema_properties["signature"]["title"] == (
        "Signature of the Authorized Certifying Official"
    )
