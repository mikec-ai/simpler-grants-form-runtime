import dataclasses

from src.form_schema.components import (
    OrganizationIdentityComponentConfig,
    build_organization_identity_component,
)


def _config(**overrides) -> OrganizationIdentityComponentConfig:
    values = {
        "organization_name_description": "Organization description",
        "sam_uei_description": "UEI description",
        "sam_uei_interaction": "null",
    }
    values.update(overrides)
    return OrganizationIdentityComponentConfig(**values)


def test_builds_organization_identity_across_all_runtime_artifacts() -> None:
    component = build_organization_identity_component(_config())

    assert component.required == ("organization_name", "sam_uei")
    assert component.json_schema_properties["organization_name"]["description"] == (
        "Organization description"
    )
    assert component.json_schema_properties["sam_uei"]["description"] == "UEI description"
    assert component.ui_schema_fields["sam_uei"] == {
        "type": "null",
        "definition": "/properties/sam_uei",
    }
    assert component.rule_schema == {"sam_uei": {"gg_pre_population": {"rule": "uei"}}}
    assert component.xml_transform_rules == {
        "organization_name": {"xml_transform": {"target": "OrganizationName"}},
        "sam_uei": {"xml_transform": {"target": "SAMUEI"}},
    }


def test_builds_independent_component_artifacts() -> None:
    first = build_organization_identity_component(_config())
    second = build_organization_identity_component(
        dataclasses.replace(_config(), sam_uei_interaction="field")
    )

    first.json_schema_properties["organization_name"]["title"] = "Changed"

    assert second.json_schema_properties["organization_name"]["title"] == "Legal Name"
    assert second.ui_schema_fields["sam_uei"]["type"] == "field"
