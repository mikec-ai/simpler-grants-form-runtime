import dataclasses
from typing import Literal

from src.form_schema.components.component_definition import (
    ComponentDefinition,
    ComponentDefinitionError,
    FieldContribution,
)

Interaction = Literal["field", "null"]

_PREPOPULATED_DESCRIPTION = "Pre-populated from the Application cover sheet."


@dataclasses.dataclass(frozen=True)
class OpportunityIdentityComponentConfig:
    """Exact presentation deltas for the shared SF-424 opportunity questions."""

    interaction: Interaction
    agency_name_title: str
    funding_opportunity_number_title: str
    funding_opportunity_title_title: str


def _field(
    *,
    field_key: str,
    title: str,
    max_length: int,
    interaction: Interaction,
    prepopulation_rule: str,
    xml_target: str,
) -> tuple[str, FieldContribution]:
    if interaction not in {"field", "null"}:
        raise ComponentDefinitionError(
            f"unsupported opportunity field interaction: {interaction!r}"
        )
    return (
        field_key,
        FieldContribution.create(
            schema={
                "type": "string",
                "title": title,
                "description": _PREPOPULATED_DESCRIPTION,
                "minLength": 1,
                "maxLength": max_length,
            },
            ui={
                "type": interaction,
                "definition": f"/properties/{field_key}",
            },
            rule={"gg_pre_population": {"rule": prepopulation_rule}},
            direct_xml={"xml_transform": {"target": xml_target}},
        ),
    )


def build_opportunity_identity_component(
    config: OpportunityIdentityComponentConfig,
) -> ComponentDefinition:
    """Build the five exact opportunity fields shared by SF-424 and SF-424 Short."""

    for title_name, title in (
        ("agency_name_title", config.agency_name_title),
        (
            "funding_opportunity_number_title",
            config.funding_opportunity_number_title,
        ),
        ("funding_opportunity_title_title", config.funding_opportunity_title_title),
    ):
        if not isinstance(title, str) or not title.strip():
            raise ComponentDefinitionError(f"{title_name} must be a nonempty string")

    return ComponentDefinition(
        component_id="application.opportunity-identity",
        contract_version=1,
        fields=(
            _field(
                field_key="agency_name",
                title=config.agency_name_title,
                max_length=60,
                interaction=config.interaction,
                prepopulation_rule="agency_name",
                xml_target="AgencyName",
            ),
            _field(
                field_key="assistance_listing_number",
                title="Assistance Listing Number",
                max_length=15,
                interaction=config.interaction,
                prepopulation_rule="assistance_listing_number",
                xml_target="CFDANumber",
            ),
            _field(
                field_key="assistance_listing_program_title",
                title="Assistance Listing Title",
                max_length=120,
                interaction=config.interaction,
                prepopulation_rule="assistance_listing_program_title",
                xml_target="CFDAProgramTitle",
            ),
            _field(
                field_key="funding_opportunity_number",
                title=config.funding_opportunity_number_title,
                max_length=40,
                interaction=config.interaction,
                prepopulation_rule="opportunity_number",
                xml_target="FundingOpportunityNumber",
            ),
            _field(
                field_key="funding_opportunity_title",
                title=config.funding_opportunity_title_title,
                max_length=255,
                interaction=config.interaction,
                prepopulation_rule="opportunity_title",
                xml_target="FundingOpportunityTitle",
            ),
        ),
    )
