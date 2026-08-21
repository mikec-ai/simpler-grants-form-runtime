import pytest

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.components.country_aware_address import build_country_aware_address_component


def test_mounts_exact_global_library_v2_wire_shape_and_country_behavior() -> None:
    mounted = build_country_aware_address_component().mount_wire(
        "/properties/AORInfo/properties/Address",
        child_namespace="globLib",
    )

    assert mounted.component_id == "people.country-aware-address.global-library-v2"
    assert mounted.json_schema["required"] == ["City", "Country", "Street1"]
    assert list(mounted.json_schema["properties"]) == [
        "Street1",
        "Street2",
        "City",
        "County",
        "State",
        "Province",
        "ZipPostalCode",
        "Country",
    ]
    assert mounted.json_schema["properties"]["Country"]["enum"][58] == ("CIV: CÔTE D’IVOIRE")
    assert mounted.json_schema["allOf"] == [
        {
            "if": {
                "properties": {"Country": {"const": "USA: UNITED STATES"}},
                "required": ["Country"],
            },
            "then": {
                "required": ["State", "ZipPostalCode"],
                "properties": {"ZipPostalCode": {"minLength": 9}},
            },
        }
    ]

    ui_by_field = {field["definition"].rsplit("/", 1)[-1]: field for field in mounted.ui_fields}
    assert list(ui_by_field) == [
        "City",
        "Country",
        "County",
        "Province",
        "State",
        "Street1",
        "Street2",
        "ZipPostalCode",
    ]
    assert ui_by_field["State"]["conditional"]["when"]["value"] == ("USA: UNITED STATES")
    assert ui_by_field["Province"]["conditional"]["when"]["op"] == "all"
    assert mounted.xml_fields["Street1"] == {
        "xml_transform": {"target": "Street1", "namespace": "globLib"}
    }


def test_inherited_xml_profile_omits_child_namespace() -> None:
    mounted = build_country_aware_address_component().mount_wire(
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/Address",
        child_namespace="inherit",
    )

    assert mounted.xml_fields["Country"] == {"xml_transform": {"target": "Country"}}


@pytest.mark.parametrize(
    ("pointer", "namespace"),
    [
        ("", "globLib"),
        ("/properties/people/items", "globLib"),
        ("/properties/Address", "invented"),
    ],
)
def test_mount_fails_closed(pointer: str, namespace: str) -> None:
    with pytest.raises(ComponentDefinitionError):
        build_country_aware_address_component().mount_wire(
            pointer,
            child_namespace=namespace,  # type: ignore[arg-type]
        )


def test_mounts_are_independently_allocated() -> None:
    definition = build_country_aware_address_component()
    first = definition.mount_wire(
        "/properties/AORInfo/properties/Address", child_namespace="globLib"
    )
    second = definition.mount_wire(
        "/properties/PDPIContactInfo/properties/Address",
        child_namespace="globLib",
    )

    first.json_schema["properties"]["City"]["title"] = "Changed"
    first.ui_fields[0]["definition"] = "Changed"
    first.xml_fields["City"]["xml_transform"]["target"] = "Changed"

    assert second.json_schema["properties"]["City"]["title"] == "City"
    assert second.ui_fields[0]["definition"].endswith("/City")
    assert second.xml_fields["City"]["xml_transform"]["target"] == "City"
