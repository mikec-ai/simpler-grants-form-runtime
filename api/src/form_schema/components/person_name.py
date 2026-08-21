import dataclasses
import json
import re
from typing import Literal

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.shared import COMMON_SHARED_V1

PersonNameXmlProfile = Literal[
    "full_global",
    "first_last_global",
    "first_last_defaulted_global",
]

_MOUNT_POINTER = re.compile(r"^/properties/[a-z][a-z0-9_]*$")
_NAME_PARTS = (
    ("prefix", "PrefixName"),
    ("first_name", "FirstName"),
    ("middle_name", "MiddleName"),
    ("last_name", "LastName"),
    ("suffix", "SuffixName"),
)


@dataclasses.dataclass(frozen=True)
class PersonNameComponentConfig:
    title: str
    description: str


@dataclasses.dataclass(frozen=True)
class MountedPersonName:
    component_id: str
    contract_version: int
    json_schema: dict
    ui_fields: tuple[dict, ...]
    xml_fields: dict


@dataclasses.dataclass(frozen=True)
class PersonNameDefinition:
    component_id: str
    contract_version: int
    _schema_json: str

    def mount(
        self, base_definition: str, *, xml_profile: PersonNameXmlProfile
    ) -> MountedPersonName:
        if not isinstance(base_definition, str) or not _MOUNT_POINTER.fullmatch(base_definition):
            raise ComponentDefinitionError("person name must mount at a root object property")
        if xml_profile not in {
            "full_global",
            "first_last_global",
            "first_last_defaulted_global",
        }:
            raise ComponentDefinitionError(f"unsupported person-name XML profile: {xml_profile!r}")

        parts = (
            _NAME_PARTS
            if xml_profile == "full_global"
            else tuple(
                (field, target)
                for field, target in _NAME_PARTS
                if field in {"first_name", "last_name"}
            )
        )
        xml_fields: dict = {}
        for field, target in parts:
            transform: dict = {"target": target, "namespace": "globLib"}
            if xml_profile == "first_last_defaulted_global":
                transform.update(
                    {
                        "null_handling": "default_value",
                        "default_value": "John" if field == "first_name" else "Doe",
                    }
                )
            xml_fields[field] = {"xml_transform": transform}

        return MountedPersonName(
            component_id=self.component_id,
            contract_version=self.contract_version,
            json_schema=json.loads(self._schema_json),
            ui_fields=tuple(
                {
                    "type": "field",
                    "definition": f"{base_definition}/properties/{field}",
                }
                for field, _ in _NAME_PARTS
            ),
            xml_fields=xml_fields,
        )


def build_person_name_component(
    config: PersonNameComponentConfig,
) -> PersonNameDefinition:
    """Build the exact shared five-part person-name schema contribution."""

    if not isinstance(config.title, str) or not config.title.strip():
        raise ComponentDefinitionError("person-name title must be a nonempty string")
    if not isinstance(config.description, str):
        raise ComponentDefinitionError("person-name description must be a string")

    schema = {
        "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("person_name")}],
        "title": config.title,
        "description": config.description,
    }
    return PersonNameDefinition(
        component_id="people.person-name",
        contract_version=1,
        _schema_json=json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
    )
