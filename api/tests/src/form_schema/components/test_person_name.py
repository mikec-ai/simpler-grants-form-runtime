import pytest

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.components.person_name import (
    PersonNameComponentConfig,
    build_person_name_component,
)
from src.form_schema.shared import COMMON_SHARED_V1


def _definition():
    return build_person_name_component(
        PersonNameComponentConfig(title="Contact Person", description="Enter the name.")
    )


def test_mounts_exact_schema_and_five_ui_fields() -> None:
    mounted = _definition().mount("/properties/contact_person", xml_profile="full_global")

    assert mounted.json_schema == {
        "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("person_name")}],
        "title": "Contact Person",
        "description": "Enter the name.",
    }
    assert [field["definition"] for field in mounted.ui_fields] == [
        f"/properties/contact_person/properties/{part}"
        for part in ("prefix", "first_name", "middle_name", "last_name", "suffix")
    ]
    assert list(mounted.xml_fields) == [
        "prefix",
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
    ]


def test_partial_and_defaulted_xml_profiles_are_explicit() -> None:
    partial = _definition().mount("/properties/contact_person", xml_profile="first_last_global")
    defaulted = _definition().mount(
        "/properties/authorized_representative",
        xml_profile="first_last_defaulted_global",
    )

    assert list(partial.xml_fields) == ["first_name", "last_name"]
    assert defaulted.xml_fields["first_name"]["xml_transform"] == {
        "target": "FirstName",
        "namespace": "globLib",
        "null_handling": "default_value",
        "default_value": "John",
    }
    assert defaulted.xml_fields["last_name"]["xml_transform"]["default_value"] == ("Doe")


@pytest.mark.parametrize("pointer", ["", "/$defs/name", "/properties/people/items"])
def test_rejects_non_root_mounts(pointer: str) -> None:
    with pytest.raises(ComponentDefinitionError, match="must mount"):
        _definition().mount(pointer, xml_profile="full_global")


def test_rejects_invalid_config_and_profile() -> None:
    with pytest.raises(ComponentDefinitionError, match="title"):
        build_person_name_component(PersonNameComponentConfig(title=" ", description="Description"))
    with pytest.raises(ComponentDefinitionError, match="unsupported"):
        _definition().mount(
            "/properties/contact_person", xml_profile="invented"  # type: ignore[arg-type]
        )


def test_mounts_are_independently_allocated() -> None:
    definition = _definition()
    first = definition.mount("/properties/contact_person", xml_profile="full_global")
    second = definition.mount("/properties/contact_person", xml_profile="full_global")

    first.json_schema["title"] = "Changed"
    first.xml_fields["first_name"]["xml_transform"]["target"] = "Changed"

    assert second.json_schema["title"] == "Contact Person"
    assert second.xml_fields["first_name"]["xml_transform"]["target"] == "FirstName"
