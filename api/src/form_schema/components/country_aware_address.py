import dataclasses
import json
import re
from typing import Literal

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.shared import ADDRESS_SHARED_V1

AddressChildNamespace = Literal["inherit", "globLib"]

_WIRE_MOUNT_POINTER = re.compile(
    r"^/properties/[A-Za-z][A-Za-z0-9_]*(?:/properties/[A-Za-z][A-Za-z0-9_]*)*$"
)
_USA = "USA: UNITED STATES"
_ALIASES = {
    "street1": "Street1",
    "street2": "Street2",
    "city": "City",
    "county": "County",
    "state": "State",
    "province": "Province",
    "zip_code": "ZipPostalCode",
    "country": "Country",
}
_UI_ORDER = (
    "city",
    "country",
    "county",
    "province",
    "state",
    "street1",
    "street2",
    "zip_code",
)


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _global_library_v2_countries() -> list[str]:
    """Return the exact V2 wire values without changing Simpler's shared enum."""

    countries = list(ADDRESS_SHARED_V1.json_schema["country_code"]["enum"])
    legacy_value = "CIV: CÔTE D'IVOIRE"
    if countries.count(legacy_value) != 1:
        raise ComponentDefinitionError("unexpected shared country-code source values")
    countries[countries.index(legacy_value)] = "CIV: CÔTE D’IVOIRE"
    return countries


def _field_schema(field: str) -> dict:
    source_key = {
        "street1": "street1",
        "street2": "street2",
        "city": "city",
        "county": "address",
        "state": "state_code",
        "province": "address",
        "zip_code": "zip_code",
        "country": "country_code",
    }[field]
    if field in {"county", "province"}:
        source = ADDRESS_SHARED_V1.json_schema[source_key]["properties"][field]
    else:
        source = ADDRESS_SHARED_V1.json_schema[source_key]
    schema = _json_copy(source)
    assert isinstance(schema, dict)
    schema.pop("description", None)
    schema["title"] = _ALIASES[field]
    if field == "country":
        schema["enum"] = _global_library_v2_countries()
    return schema


def _data_pointer(schema_pointer: str) -> str:
    return schema_pointer.replace("/properties/", "/")


def _show_when(predicate: dict) -> dict:
    return {
        "when": predicate,
        "then": {"visible": True},
        "otherwise": {"visible": False},
    }


@dataclasses.dataclass(frozen=True)
class MountedCountryAwareAddress:
    component_id: str
    contract_version: int
    json_schema: dict
    ui_fields: tuple[dict, ...]
    xml_fields: dict


@dataclasses.dataclass(frozen=True)
class CountryAwareAddressDefinition:
    """Exact Global Library V2 address contribution with reviewed country behavior."""

    component_id: str = "people.country-aware-address.global-library-v2"
    contract_version: int = 1

    def mount_wire(
        self,
        base_definition: str,
        *,
        child_namespace: AddressChildNamespace,
    ) -> MountedCountryAwareAddress:
        if not isinstance(base_definition, str) or not _WIRE_MOUNT_POINTER.fullmatch(
            base_definition
        ):
            raise ComponentDefinitionError(
                "country-aware address must mount at a nested object-property pointer"
            )
        if child_namespace not in {"inherit", "globLib"}:
            raise ComponentDefinitionError(
                f"unsupported address child namespace: {child_namespace!r}"
            )

        country_pointer = f"{_data_pointer(base_definition)}/Country"
        is_usa = {
            "op": "equals",
            "ref": {"scope": "root", "pointer": country_pointer},
            "value": _USA,
        }
        is_non_usa = {
            "op": "all",
            "predicates": [
                {
                    "op": "present",
                    "ref": {"scope": "root", "pointer": country_pointer},
                },
                {
                    "op": "notEquals",
                    "ref": {"scope": "root", "pointer": country_pointer},
                    "value": _USA,
                },
            ],
        }

        schema = {
            "type": "object",
            "required": ["City", "Country", "Street1"],
            "allOf": [
                {
                    "if": {
                        "properties": {"Country": {"const": _USA}},
                        "required": ["Country"],
                    },
                    "then": {
                        "required": ["State", "ZipPostalCode"],
                        "properties": {"ZipPostalCode": {"minLength": 9}},
                    },
                }
            ],
            "properties": {alias: _field_schema(field) for field, alias in _ALIASES.items()},
        }

        ui_fields: list[dict] = []
        for field in _UI_ORDER:
            alias = _ALIASES[field]
            ui_field: dict[str, object] = {
                "type": "field",
                "definition": f"{base_definition}/properties/{alias}",
            }
            if field in {"state", "zip_code"}:
                ui_field["conditional"] = _show_when(is_usa)
            elif field == "province":
                ui_field["conditional"] = _show_when(is_non_usa)
            ui_fields.append(ui_field)

        xml_fields: dict[str, dict] = {}
        for alias in _ALIASES.values():
            transform: dict[str, str] = {"target": alias}
            if child_namespace == "globLib":
                transform["namespace"] = "globLib"
            xml_fields[alias] = {"xml_transform": transform}

        return MountedCountryAwareAddress(
            component_id=self.component_id,
            contract_version=self.contract_version,
            json_schema=schema,
            ui_fields=tuple(ui_fields),
            xml_fields=xml_fields,
        )


def build_country_aware_address_component() -> CountryAwareAddressDefinition:
    return CountryAwareAddressDefinition()
