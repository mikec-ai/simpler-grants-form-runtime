import dataclasses
import json
import re
from typing import Literal

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.shared import ADDRESS_SHARED_V1, COMMON_SHARED_V1

ContactProfile = Literal["key_contacts", "global_contact_person_v3"]

_MOUNT_POINTER = re.compile(
    r"^/properties/[a-z][a-z0-9_]*(?:/(?:items|properties/[a-z][a-z0-9_]*))*$"
)


@dataclasses.dataclass(frozen=True)
class MountedContactProfile:
    """Fresh runtime contributions for one explicitly mounted contact profile."""

    json_schema_definition: dict
    ui_fields: dict[str, tuple[dict, ...]]
    xml_fields: dict


@dataclasses.dataclass(frozen=True)
class ContactProfileDefinition:
    """Immutable profile whose two variants correspond to proven native shapes."""

    component_id: str
    contract_version: int
    _schema_json: str
    _ui_suffixes_json: str
    _xml_json: str

    def mount(self, base_definition: str) -> MountedContactProfile:
        if not isinstance(base_definition, str) or not _MOUNT_POINTER.fullmatch(base_definition):
            raise ComponentDefinitionError(
                "contact profile must mount at a root object or array-item pointer"
            )

        suffixes: dict[str, list[str]] = json.loads(self._ui_suffixes_json)
        return MountedContactProfile(
            json_schema_definition=json.loads(self._schema_json),
            ui_fields={
                field: tuple(
                    {"type": "field", "definition": f"{base_definition}{suffix}"}
                    for suffix in field_suffixes
                )
                for field, field_suffixes in suffixes.items()
            },
            xml_fields=json.loads(self._xml_json),
        )


def _field_schema(*, ref: str, title: str | None = None) -> dict:
    schema: dict = {"allOf": [{"$ref": ref}]}
    if title is not None:
        schema["title"] = title
    return schema


def _nested_xml(
    *,
    target: str,
    children: tuple[tuple[str, str], ...],
    namespace: str | None,
) -> dict:
    transform: dict = {"target": target, "type": "nested_object"}
    if namespace is not None:
        transform["namespace"] = namespace
    result: dict = {"xml_transform": transform}
    for field, child_target in children:
        result[field] = {"xml_transform": {"target": child_target, "namespace": "globLib"}}
    return result


def _direct_xml(*, target: str, namespace: str | None) -> dict:
    transform = {"target": target}
    if namespace is not None:
        transform["namespace"] = namespace
    return {"xml_transform": transform}


def _xml_name(field: str) -> str:
    return {
        "street1": "Street1",
        "street2": "Street2",
        "city": "City",
        "county": "County",
        "state": "State",
        "province": "Province",
        "country": "Country",
    }[field]


def build_contact_profile_component(profile: ContactProfile) -> ContactProfileDefinition:
    """Build one of the two exact contact shapes already present in Simpler."""

    if profile not in {"key_contacts", "global_contact_person_v3"}:
        raise ComponentDefinitionError(f"unsupported contact profile: {profile!r}")

    is_key_contacts = profile == "key_contacts"
    address_ref = ADDRESS_SHARED_V1.field_ref(
        "address" if is_key_contacts else "simple_address_with_country"
    )
    required = ["name", "address", "phone"]
    if is_key_contacts:
        required.append("email")

    schema = {
        "type": "object",
        "required": required,
        "properties": {
            "name": _field_schema(ref=COMMON_SHARED_V1.field_ref("person_name"), title="Name"),
            "title": _field_schema(
                ref=COMMON_SHARED_V1.field_ref("contact_person_title"), title="Title"
            ),
            "address": _field_schema(ref=address_ref),
            "phone": _field_schema(
                ref=COMMON_SHARED_V1.field_ref("phone_number"),
                title="Telephone Number" if is_key_contacts else "Phone Number",
            ),
            "fax": _field_schema(
                ref=COMMON_SHARED_V1.field_ref("phone_number"), title="Fax Number"
            ),
            "email": _field_schema(
                ref=COMMON_SHARED_V1.field_ref("contact_email"),
                title="Email" if is_key_contacts else "E-mail Address",
            ),
        },
    }

    name_suffixes = tuple(
        f"/properties/name/properties/{field}"
        for field in ("prefix", "first_name", "middle_name", "last_name", "suffix")
    )
    ui_address_fields = (
        (
            "street1",
            "street2",
            "city",
            "county",
            "state",
            "province",
            "country",
            "zip_code",
        )
        if is_key_contacts
        else ("street1", "street2", "city", "state", "zip_code", "country")
    )
    xml_address_fields = (
        (
            "street1",
            "street2",
            "city",
            "county",
            "state",
            "province",
            "zip_code",
            "country",
        )
        if is_key_contacts
        else ui_address_fields
    )
    ui_suffixes = {
        "name": name_suffixes,
        "title": ("/properties/title",),
        "address": tuple(f"/properties/address/properties/{field}" for field in ui_address_fields),
        "phone": ("/properties/phone",),
        "fax": ("/properties/fax",),
        "email": ("/properties/email",),
    }

    direct_namespace = None if is_key_contacts else "globLib"
    xml_fields = {
        "name": _nested_xml(
            target="ContactName" if is_key_contacts else "Name",
            children=(
                ("prefix", "PrefixName"),
                ("first_name", "FirstName"),
                ("middle_name", "MiddleName"),
                ("last_name", "LastName"),
                ("suffix", "SuffixName"),
            ),
            namespace=direct_namespace,
        ),
        "title": _direct_xml(
            target="ContactTitle" if is_key_contacts else "Title",
            namespace=direct_namespace,
        ),
        "address": _nested_xml(
            target="ContactAddress" if is_key_contacts else "Address",
            children=tuple(
                (field, "ZipPostalCode" if field == "zip_code" else _xml_name(field))
                for field in xml_address_fields
            ),
            namespace=direct_namespace,
        ),
        "phone": _direct_xml(
            target="ContactPhone" if is_key_contacts else "Phone",
            namespace=direct_namespace,
        ),
        "fax": _direct_xml(
            target="ContactFax" if is_key_contacts else "Fax",
            namespace=direct_namespace,
        ),
        "email": _direct_xml(
            target="ContactEmail" if is_key_contacts else "Email",
            namespace=direct_namespace,
        ),
    }

    return ContactProfileDefinition(
        component_id=f"people.contact-profile.{profile.replace('_', '-')}",
        contract_version=1,
        _schema_json=json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
        _ui_suffixes_json=json.dumps(ui_suffixes, ensure_ascii=False, separators=(",", ":")),
        _xml_json=json.dumps(xml_fields, ensure_ascii=False, separators=(",", ":")),
    )
