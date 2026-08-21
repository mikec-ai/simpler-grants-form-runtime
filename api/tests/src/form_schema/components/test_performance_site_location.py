import pytest

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.components.performance_site_location import build_performance_site_location


def test_performance_site_profiles_share_structure_and_preserve_real_delta() -> None:
    primary = build_performance_site_location(
        "/properties/primary_site", require_organization_unless_individual=True
    )
    additional = build_performance_site_location(
        "/properties/additional_sites/items",
        require_organization_unless_individual=False,
    )

    assert primary.component_id == "application.performance-site-location"
    assert primary.json_schema["properties"] == additional.json_schema["properties"]
    assert primary.xml_fields == additional.xml_fields
    assert len(primary.json_schema["allOf"]) == 2
    assert len(additional.json_schema["allOf"]) == 1
    assert primary.ui_fields[3]["definition"] == (
        "/properties/primary_site/properties/address/properties/street1"
    )
    assert additional.ui_fields[3]["definition"] == (
        "/properties/additional_sites/items/properties/address/properties/street1"
    )


@pytest.mark.parametrize("pointer", ["", "/$defs/site", "/properties/Site", 4])
def test_performance_site_rejects_unsupported_mounts(pointer: object) -> None:
    with pytest.raises(ComponentDefinitionError, match="schema property pointer"):
        build_performance_site_location(
            pointer,  # type: ignore[arg-type]
            require_organization_unless_individual=False,
        )


def test_performance_site_allocates_independent_artifacts() -> None:
    first = build_performance_site_location(
        "/properties/primary_site", require_organization_unless_individual=True
    )
    second = build_performance_site_location(
        "/properties/primary_site", require_organization_unless_individual=True
    )
    first.json_schema["properties"]["organization_name"]["title"] = "mutated"
    assert second.json_schema["properties"]["organization_name"]["title"] == ("Organization Name")
