import dataclasses

import pytest

from src.form_schema.components import (
    ComponentDefinition,
    ComponentDefinitionError,
    FieldContribution,
    OrganizationIdentityComponentConfig,
    OrganizationNameComponentConfig,
    SamUeiComponentConfig,
    build_organization_identity_component,
    build_organization_name_component,
    build_sam_uei_component,
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
    component = build_organization_identity_component(_config()).mount_root()

    assert component.component_id == "application.organization-identity.sf424-profile"
    assert component.json_schema_properties["organization_name"]["description"] == (
        "Organization description"
    )
    assert component.json_schema_properties["sam_uei"]["description"] == ("UEI description")
    assert component.ui_schema_fields["sam_uei"] == {
        "type": "null",
        "definition": "/properties/sam_uei",
    }
    assert component.rule_schema == {"sam_uei": {"gg_pre_population": {"rule": "uei"}}}
    assert component.xml_transform_rules == {
        "organization_name": {"xml_transform": {"target": "OrganizationName"}},
        "sam_uei": {"xml_transform": {"target": "SAMUEI"}},
    }


def test_atomic_organization_name_can_be_aliased_at_the_form_root() -> None:
    component = build_organization_name_component(
        OrganizationNameComponentConfig(
            title="Applicant Name",
            description="Applicant organization",
            source_question_binding="QuestionOrgName",
        )
    ).mount_root(aliases={"organization_name": "applicant_name"})

    assert component.json_schema_properties == {
        "applicant_name": {
            "allOf": [
                {
                    "$ref": "https://files.simpler.grants.gov/schemas/"
                    "common_shared_v1.json#/organization_name"
                }
            ],
            "title": "Applicant Name",
            "description": "Applicant organization",
        }
    }
    assert component.ui_schema_fields["applicant_name"]["definition"] == (
        "/properties/applicant_name"
    )
    assert component.rule_schema == {}
    assert component.xml_transform_rules["applicant_name"] == {
        "xml_transform": {"target": "OrganizationName"}
    }
    assert component.source_question_bindings == {"applicant_name": "QuestionOrgName"}


def test_mount_returns_independently_allocated_artifacts() -> None:
    definition = build_organization_identity_component(_config())
    first = definition.mount_root()
    second = definition.mount_root()

    first.json_schema_properties["organization_name"]["title"] = "Changed"
    first.ui_schema_fields["sam_uei"]["type"] = "field"
    first.rule_schema["sam_uei"]["gg_pre_population"]["rule"] = "changed"

    assert second.json_schema_properties["organization_name"]["title"] == "Legal Name"
    assert second.ui_schema_fields["sam_uei"]["type"] == "null"
    assert second.rule_schema["sam_uei"]["gg_pre_population"]["rule"] == "uei"


@pytest.mark.parametrize("interaction", ["hidden", "readonly", "invalid"])
def test_rejects_unsupported_runtime_interaction(interaction: str) -> None:
    with pytest.raises(ComponentDefinitionError, match="unsupported field interaction"):
        build_organization_name_component(
            OrganizationNameComponentConfig(
                title="Name", description="Description", interaction=interaction
            )
        )


def test_rejects_unsupported_runtime_prepopulation() -> None:
    with pytest.raises(ComponentDefinitionError, match="unsupported SAM UEI"):
        build_sam_uei_component(
            SamUeiComponentConfig(
                title="SAM UEI",
                description="Description",
                interaction="field",
                prepopulation="copy",
            )
        )


@pytest.mark.parametrize(
    ("aliases", "reserved", "message"),
    [
        ({"unknown": "name"}, (), "unknown component fields"),
        ({"organization_name": "group.name"}, (), "root field key"),
        ({"organization_name": "sam_uei"}, (), "duplicate destination"),
        ({}, ("organization_name",), "collide with reserved"),
    ],
)
def test_mount_rejects_unsafe_aliases_and_collisions(
    aliases: dict[str, str], reserved: tuple[str, ...], message: str
) -> None:
    definition = build_organization_identity_component(_config())

    with pytest.raises(ComponentDefinitionError, match=message):
        definition.mount_root(aliases=aliases, reserved_fields=reserved)


def test_definition_rejects_ui_pointer_outside_its_field() -> None:
    contribution = FieldContribution.create(
        schema={"type": "string"},
        ui={"type": "field", "definition": "/properties/other"},
    )

    with pytest.raises(ComponentDefinitionError, match="target its own root property"):
        ComponentDefinition(
            component_id="application.example",
            contract_version=1,
            fields=(("name", contribution),),
        )


@pytest.mark.parametrize(
    ("contribution", "message"),
    [
        (
            FieldContribution.create(
                schema={"type": "string"},
                ui={
                    "type": "field",
                    "definition": "/properties/name",
                    "children": [],
                },
            ),
            "only type and definition",
        ),
        (
            FieldContribution.create(
                schema={"type": "string"},
                ui={"type": "field", "definition": "/properties/name"},
                rule={"invented_runtime": {"effect": "anything"}},
            ),
            "unsupported behavior",
        ),
        (
            FieldContribution.create(
                schema={"type": "string"},
                ui={"type": "field", "definition": "/properties/name"},
                direct_xml={
                    "xml_transform": {"target": "Name"},
                    "items": {},
                },
            ),
            "only xml_transform",
        ),
        (
            FieldContribution.create(
                schema={"type": "string"},
                ui={"type": "field", "definition": "/properties/name"},
                direct_xml={"xml_transform": {"target": ""}},
            ),
            "target must be a nonempty string",
        ),
        (
            FieldContribution.create(
                schema={"type": "string"},
                ui={"type": "field", "definition": "/properties/name"},
                direct_xml={"xml_transform": {"target": "Name", "namespace": 3}},
            ),
            "namespace must be a nonempty string",
        ),
        (
            FieldContribution.create(
                schema={"type": "string"},
                ui={"type": "field", "definition": "/properties/name"},
                source_question_binding="not a question id",
            ),
            "source question binding is invalid",
        ),
    ],
)
def test_definition_rejects_behavior_outside_v1_contract(
    contribution: FieldContribution, message: str
) -> None:
    with pytest.raises(ComponentDefinitionError, match=message):
        ComponentDefinition(
            component_id="application.example",
            contract_version=1,
            fields=(("name", contribution),),
        )


def test_definition_requires_at_least_one_field() -> None:
    with pytest.raises(ComponentDefinitionError, match="at least one field"):
        ComponentDefinition(component_id="application.example", contract_version=1, fields=())


def test_profile_variants_do_not_share_mutable_artifacts() -> None:
    first = build_organization_identity_component(_config()).mount_root()
    second = build_organization_identity_component(
        dataclasses.replace(_config(), sam_uei_interaction="field")
    ).mount_root()

    first.json_schema_properties["organization_name"]["title"] = "Changed"

    assert second.json_schema_properties["organization_name"]["title"] == "Legal Name"
    assert second.ui_schema_fields["sam_uei"]["type"] == "field"
