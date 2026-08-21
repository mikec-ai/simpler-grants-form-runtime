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
            "/properties/contact_person",
            xml_profile="invented",  # type: ignore[arg-type]
        )


def test_mounts_are_independently_allocated() -> None:
    definition = _definition()
    first = definition.mount("/properties/contact_person", xml_profile="full_global")
    second = definition.mount("/properties/contact_person", xml_profile="full_global")

    first.json_schema["title"] = "Changed"
    first.xml_fields["first_name"]["xml_transform"]["target"] = "Changed"

    assert second.json_schema["title"] == "Contact Person"
    assert second.xml_fields["first_name"]["xml_transform"]["target"] == "FirstName"


def test_component_can_preserve_an_unlabelled_source_schema() -> None:
    mounted = build_person_name_component(PersonNameComponentConfig()).mount(
        "/properties/authorized_representative_name", xml_profile="full_global"
    )

    assert mounted.json_schema == {"allOf": [{"$ref": COMMON_SHARED_V1.field_ref("person_name")}]}


def test_mounts_source_bound_wire_aliases_without_changing_canonical_constraints() -> None:
    mounted = _definition().mount_wire(
        "/properties/AORInfo/properties/Name",
        aliases={
            "prefix": "PrefixName",
            "first_name": "FirstName",
            "middle_name": "MiddleName",
            "last_name": "LastName",
            "suffix": "SuffixName",
        },
        ui_order=("first_name", "last_name", "middle_name", "prefix", "suffix"),
    )

    assert mounted.json_schema["required"] == ["FirstName", "LastName"]
    assert mounted.json_schema["properties"]["FirstName"] == {
        "type": "string",
        "title": "FirstName",
        "minLength": 1,
        "maxLength": 35,
    }
    assert [field["definition"] for field in mounted.ui_fields] == [
        f"/properties/AORInfo/properties/Name/properties/{field}"
        for field in ("FirstName", "LastName", "MiddleName", "PrefixName", "SuffixName")
    ]
    assert mounted.xml_fields["PrefixName"] == {
        "xml_transform": {"target": "PrefixName", "namespace": "globLib"}
    }


@pytest.mark.parametrize(
    ("aliases", "ui_order"),
    [
        ({"first_name": "FirstName"}, ("first_name",)),
        (
            {
                "prefix": "Name",
                "first_name": "Name",
                "middle_name": "MiddleName",
                "last_name": "LastName",
                "suffix": "SuffixName",
            },
            ("prefix", "first_name", "middle_name", "last_name", "suffix"),
        ),
    ],
)
def test_wire_mount_fails_closed_for_incomplete_or_duplicate_aliases(
    aliases: dict[str, str], ui_order: tuple[str, ...]
) -> None:
    with pytest.raises(ComponentDefinitionError):
        _definition().mount_wire(
            "/properties/AORInfo/properties/Name",
            aliases=aliases,
            ui_order=ui_order,
        )
