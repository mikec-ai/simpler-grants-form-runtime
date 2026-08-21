import pytest

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.components.contact_profile import build_contact_profile_component
from src.form_schema.shared import ADDRESS_SHARED_V1


def test_key_contacts_profile_preserves_exact_schema_and_mount_paths() -> None:
    mounted = build_contact_profile_component("key_contacts").mount(
        "/properties/key_contacts/items"
    )

    assert mounted.json_schema_definition["required"] == [
        "name",
        "address",
        "phone",
        "email",
    ]
    assert mounted.json_schema_definition["properties"]["address"] == {
        "allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("address")}]
    }
    assert mounted.json_schema_definition["properties"]["phone"]["title"] == ("Telephone Number")
    assert [node["definition"] for node in mounted.ui_fields["address"]] == [
        f"/properties/key_contacts/items/properties/address/properties/{field}"
        for field in (
            "street1",
            "street2",
            "city",
            "county",
            "state",
            "province",
            "country",
            "zip_code",
        )
    ]
    assert mounted.xml_fields["name"]["xml_transform"] == {
        "target": "ContactName",
        "type": "nested_object",
    }
    assert mounted.xml_fields["email"] == {"xml_transform": {"target": "ContactEmail"}}


def test_global_contact_profile_preserves_exact_variant_deltas() -> None:
    mounted = build_contact_profile_component("global_contact_person_v3").mount(
        "/properties/authorized_representative"
    )

    assert mounted.json_schema_definition["required"] == ["name", "address", "phone"]
    assert mounted.json_schema_definition["properties"]["address"] == {
        "allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("simple_address_with_country")}]
    }
    assert mounted.json_schema_definition["properties"]["email"]["title"] == ("E-mail Address")
    assert mounted.xml_fields["address"]["xml_transform"] == {
        "target": "Address",
        "type": "nested_object",
        "namespace": "globLib",
    }
    assert mounted.xml_fields["phone"] == {
        "xml_transform": {"target": "Phone", "namespace": "globLib"}
    }


def test_sf424_short_profile_preserves_exact_native_shape() -> None:
    mounted = build_contact_profile_component("sf424_short_contact_person_v3").mount(
        "/properties/project_director"
    )

    assert mounted.json_schema_definition["required"] == [
        "name",
        "title",
        "address",
        "phone_number",
        "email",
    ]
    properties = mounted.json_schema_definition["properties"]
    assert properties["name"]["description"] == "Enter the name."
    assert properties["address"] == {
        "allOf": [{"$ref": ADDRESS_SHARED_V1.field_ref("address")}],
        "title": "Address",
        "description": "Enter the address.",
    }
    assert properties["phone_number"]["description"] == ("Enter the daytime Telephone Number.")
    assert mounted.ui_fields["phone_number"] == (
        {
            "type": "field",
            "definition": "/properties/project_director/properties/phone_number",
        },
    )
    assert mounted.xml_fields["phone_number"] == {
        "xml_transform": {"target": "Phone", "namespace": "globLib"}
    }
    assert list(mounted.xml_fields["address"])[-2:] == ["zip_code", "country"]


@pytest.mark.parametrize(
    "pointer",
    ["", "/$defs/contact", "/properties/contacts/0", "/properties/contacts/items/name"],
)
def test_rejects_unsupported_mount_pointers(pointer: str) -> None:
    with pytest.raises(ComponentDefinitionError, match="must mount"):
        build_contact_profile_component("key_contacts").mount(pointer)


def test_rejects_unknown_profile() -> None:
    with pytest.raises(ComponentDefinitionError, match="unsupported contact profile"):
        build_contact_profile_component("invented")  # type: ignore[arg-type]


def test_mounts_are_independently_allocated() -> None:
    definition = build_contact_profile_component("key_contacts")
    first = definition.mount("/properties/key_contacts/items")
    second = definition.mount("/properties/key_contacts/items")

    first.json_schema_definition["properties"]["name"]["title"] = "Changed"
    first.xml_fields["name"]["xml_transform"]["target"] = "Changed"

    assert second.json_schema_definition["properties"]["name"]["title"] == "Name"
    assert second.xml_fields["name"]["xml_transform"]["target"] == "ContactName"
