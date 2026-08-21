import dataclasses
from typing import Literal

from src.form_schema.components.component_definition import (
    ComponentDefinition,
    ComponentDefinitionError,
    FieldContribution,
)
from src.form_schema.shared import COMMON_SHARED_V1

Interaction = Literal["field", "null"]
Prepopulation = Literal["uei", "none"]


@dataclasses.dataclass(frozen=True)
class OrganizationNameComponentConfig:
    title: str
    description: str
    interaction: Interaction = "field"
    source_question_binding: str | None = None


@dataclasses.dataclass(frozen=True)
class SamUeiComponentConfig:
    title: str
    description: str
    interaction: Interaction
    prepopulation: Prepopulation = "uei"
    source_question_binding: str | None = None


@dataclasses.dataclass(frozen=True)
class OrganizationIdentityComponentConfig:
    """Exact SF-424 profile deltas for two atomic organization questions."""

    organization_name_description: str
    sam_uei_description: str
    sam_uei_interaction: Interaction


def _validate_interaction(value: str) -> None:
    if value not in {"field", "null"}:
        raise ComponentDefinitionError(f"unsupported field interaction: {value!r}")


def _organization_name_contribution(
    config: OrganizationNameComponentConfig,
) -> FieldContribution:
    _validate_interaction(config.interaction)
    return FieldContribution.create(
        schema={
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("organization_name")}],
            "title": config.title,
            "description": config.description,
        },
        ui={
            "type": config.interaction,
            "definition": "/properties/organization_name",
        },
        direct_xml={"xml_transform": {"target": "OrganizationName"}},
        source_question_binding=config.source_question_binding,
    )


def _sam_uei_contribution(config: SamUeiComponentConfig) -> FieldContribution:
    _validate_interaction(config.interaction)
    if config.prepopulation not in {"uei", "none"}:
        raise ComponentDefinitionError(
            f"unsupported SAM UEI prepopulation: {config.prepopulation!r}"
        )
    rule = {"gg_pre_population": {"rule": "uei"}} if config.prepopulation == "uei" else None
    return FieldContribution.create(
        schema={
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("sam_uei")}],
            "title": config.title,
            "description": config.description,
        },
        ui={
            "type": config.interaction,
            "definition": "/properties/sam_uei",
        },
        rule=rule,
        direct_xml={"xml_transform": {"target": "SAMUEI"}},
        source_question_binding=config.source_question_binding,
    )


def build_organization_name_component(
    config: OrganizationNameComponentConfig,
) -> ComponentDefinition:
    return ComponentDefinition(
        component_id="application.organization-name",
        contract_version=1,
        fields=(("organization_name", _organization_name_contribution(config)),),
    )


def build_sam_uei_component(config: SamUeiComponentConfig) -> ComponentDefinition:
    return ComponentDefinition(
        component_id="application.sam-uei",
        contract_version=1,
        fields=(("sam_uei", _sam_uei_contribution(config)),),
    )


def build_organization_identity_component(
    config: OrganizationIdentityComponentConfig,
) -> ComponentDefinition:
    """Compose the exact SF-424 organization-name and SAM UEI profile."""

    return ComponentDefinition(
        component_id="application.organization-identity.sf424-profile",
        contract_version=1,
        fields=(
            (
                "organization_name",
                _organization_name_contribution(
                    OrganizationNameComponentConfig(
                        title="Legal Name",
                        description=config.organization_name_description,
                    )
                ),
            ),
            (
                "sam_uei",
                _sam_uei_contribution(
                    SamUeiComponentConfig(
                        title="SAM UEI",
                        description=config.sam_uei_description,
                        interaction=config.sam_uei_interaction,
                    )
                ),
            ),
        ),
    )
