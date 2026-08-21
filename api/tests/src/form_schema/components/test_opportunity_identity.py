import dataclasses

import pytest

from src.form_schema.components import (
    ComponentDefinitionError,
    OpportunityIdentityComponentConfig,
    build_opportunity_identity_component,
)

_FIELDS = (
    "agency_name",
    "assistance_listing_number",
    "assistance_listing_program_title",
    "funding_opportunity_number",
    "funding_opportunity_title",
)


def _sf424_config(**overrides) -> OpportunityIdentityComponentConfig:
    values = {
        "interaction": "field",
        "agency_name_title": "Agency Name",
        "funding_opportunity_number_title": "Opportunity Number",
        "funding_opportunity_title_title": "Opportunity title",
    }
    values.update(overrides)
    return OpportunityIdentityComponentConfig(**values)


def test_builds_all_five_opportunity_fields_across_runtime_artifacts() -> None:
    component = build_opportunity_identity_component(_sf424_config()).mount_root()

    assert tuple(component.json_schema_properties) == _FIELDS
    assert component.json_schema_properties == {
        "agency_name": {
            "type": "string",
            "title": "Agency Name",
            "description": "Pre-populated from the Application cover sheet.",
            "minLength": 1,
            "maxLength": 60,
        },
        "assistance_listing_number": {
            "type": "string",
            "title": "Assistance Listing Number",
            "description": "Pre-populated from the Application cover sheet.",
            "minLength": 1,
            "maxLength": 15,
        },
        "assistance_listing_program_title": {
            "type": "string",
            "title": "Assistance Listing Title",
            "description": "Pre-populated from the Application cover sheet.",
            "minLength": 1,
            "maxLength": 120,
        },
        "funding_opportunity_number": {
            "type": "string",
            "title": "Opportunity Number",
            "description": "Pre-populated from the Application cover sheet.",
            "minLength": 1,
            "maxLength": 40,
        },
        "funding_opportunity_title": {
            "type": "string",
            "title": "Opportunity title",
            "description": "Pre-populated from the Application cover sheet.",
            "minLength": 1,
            "maxLength": 255,
        },
    }
    assert component.ui_schema_fields == {
        field: {"type": "field", "definition": f"/properties/{field}"} for field in _FIELDS
    }
    assert component.rule_schema == {
        "agency_name": {"gg_pre_population": {"rule": "agency_name"}},
        "assistance_listing_number": {"gg_pre_population": {"rule": "assistance_listing_number"}},
        "assistance_listing_program_title": {
            "gg_pre_population": {"rule": "assistance_listing_program_title"}
        },
        "funding_opportunity_number": {"gg_pre_population": {"rule": "opportunity_number"}},
        "funding_opportunity_title": {"gg_pre_population": {"rule": "opportunity_title"}},
    }
    assert component.xml_transform_rules == {
        "agency_name": {"xml_transform": {"target": "AgencyName"}},
        "assistance_listing_number": {"xml_transform": {"target": "CFDANumber"}},
        "assistance_listing_program_title": {"xml_transform": {"target": "CFDAProgramTitle"}},
        "funding_opportunity_number": {"xml_transform": {"target": "FundingOpportunityNumber"}},
        "funding_opportunity_title": {"xml_transform": {"target": "FundingOpportunityTitle"}},
    }


def test_short_profile_changes_only_titles_and_interaction() -> None:
    sf424 = build_opportunity_identity_component(_sf424_config()).mount_root()
    short = build_opportunity_identity_component(
        dataclasses.replace(
            _sf424_config(),
            interaction="null",
            agency_name_title="Name of Federal Agency",
            funding_opportunity_number_title="Funding Opportunity Number",
            funding_opportunity_title_title="Funding Opportunity Title",
        )
    ).mount_root()

    assert {field["type"] for field in short.ui_schema_fields.values()} == {"null"}
    assert short.json_schema_properties["agency_name"]["title"] == ("Name of Federal Agency")
    assert short.json_schema_properties["funding_opportunity_number"]["title"] == (
        "Funding Opportunity Number"
    )
    assert short.json_schema_properties["funding_opportunity_title"]["title"] == (
        "Funding Opportunity Title"
    )
    assert short.rule_schema == sf424.rule_schema
    assert short.xml_transform_rules == sf424.xml_transform_rules


def test_rejects_unsupported_runtime_interaction() -> None:
    with pytest.raises(ComponentDefinitionError, match="unsupported opportunity field interaction"):
        build_opportunity_identity_component(_sf424_config(interaction="hidden"))


@pytest.mark.parametrize(
    "title_field",
    [
        "agency_name_title",
        "funding_opportunity_number_title",
        "funding_opportunity_title_title",
    ],
)
def test_rejects_empty_profile_title(title_field: str) -> None:
    with pytest.raises(ComponentDefinitionError, match="must be a nonempty string"):
        build_opportunity_identity_component(_sf424_config(**{title_field: " "}))
