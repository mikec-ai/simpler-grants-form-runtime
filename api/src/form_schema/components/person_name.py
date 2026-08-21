import dataclasses
import json
import re
from collections.abc import Mapping, Sequence
from typing import Literal

from src.form_schema.components.component_definition import ComponentDefinitionError
from src.form_schema.shared import COMMON_SHARED_V1

PersonNameXmlProfile = Literal[
    "full_global",
    "first_last_global",
    "first_last_defaulted_global",
]

_MOUNT_POINTER = re.compile(r"^/properties/[a-z][a-z0-9_]*$")
_WIRE_MOUNT_POINTER = re.compile(
    r"^/properties/[A-Za-z][A-Za-z0-9_]*(?:/properties/[A-Za-z][A-Za-z0-9_]*)*$"
)
_WIRE_FIELD_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_NAME_PARTS = (
    ("prefix", "PrefixName"),
    ("first_name", "FirstName"),
    ("middle_name", "MiddleName"),
    ("last_name", "LastName"),
    ("suffix", "SuffixName"),
)


@dataclasses.dataclass(frozen=True)
class PersonNameComponentConfig:
    title: str | None = None
    description: str | None = None


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

    def mount_wire(
        self,
        base_definition: str,
        *,
        aliases: Mapping[str, str],
        ui_order: Sequence[str],
    ) -> MountedPersonName:
        """Mount the canonical name shape under exact source-bound wire aliases.

        This deliberately supports only a nested object pointer and a complete,
        one-to-one alias for the five canonical name parts. Source provenance and
        role semantics remain form-owned overlays.
        """

        if not isinstance(base_definition, str) or not _WIRE_MOUNT_POINTER.fullmatch(
            base_definition
        ):
            raise ComponentDefinitionError(
                "wire person name must mount at a nested object-property pointer"
            )

        canonical_fields = tuple(field for field, _ in _NAME_PARTS)
        alias_map = dict(aliases)
        if set(alias_map) != set(canonical_fields):
            raise ComponentDefinitionError(
                "wire person-name aliases must cover every canonical name part"
            )
        if any(
            not isinstance(alias, str) or not _WIRE_FIELD_KEY.fullmatch(alias)
            for alias in alias_map.values()
        ):
            raise ComponentDefinitionError("wire person-name aliases are invalid")
        if len(set(alias_map.values())) != len(alias_map):
            raise ComponentDefinitionError("wire person-name aliases must be unique")
        if tuple(ui_order) != tuple(dict.fromkeys(ui_order)) or set(ui_order) != set(
            canonical_fields
        ):
            raise ComponentDefinitionError(
                "wire person-name UI order must contain every canonical name part once"
            )

        canonical_schema = json.loads(json.dumps(COMMON_SHARED_V1.json_schema["person_name"]))
        schema: dict = {
            "type": "object",
            "required": [alias_map[field] for field in canonical_schema["required"]],
            "properties": {},
        }
        for field in canonical_fields:
            wire_field = alias_map[field]
            field_schema = canonical_schema["properties"][field]
            field_schema.pop("description", None)
            field_schema["title"] = wire_field
            schema["properties"][wire_field] = field_schema

        target_by_field = dict(_NAME_PARTS)
        return MountedPersonName(
            component_id=self.component_id,
            contract_version=self.contract_version,
            json_schema=schema,
            ui_fields=tuple(
                {
                    "type": "field",
                    "definition": f"{base_definition}/properties/{alias_map[field]}",
                }
                for field in ui_order
            ),
            xml_fields={
                alias_map[field]: {
                    "xml_transform": {
                        "target": target_by_field[field],
                        "namespace": "globLib",
                    }
                }
                for field in canonical_fields
            },
        )


def build_person_name_component(
    config: PersonNameComponentConfig,
) -> PersonNameDefinition:
    """Build the exact shared five-part person-name schema contribution."""

    if config.title is not None and (not isinstance(config.title, str) or not config.title.strip()):
        raise ComponentDefinitionError("person-name title must be a nonempty string")
    if config.description is not None and not isinstance(config.description, str):
        raise ComponentDefinitionError("person-name description must be a string")

    schema: dict = {"allOf": [{"$ref": COMMON_SHARED_V1.field_ref("person_name")}]}
    if config.title is not None:
        schema["title"] = config.title
    if config.description is not None:
        schema["description"] = config.description
    return PersonNameDefinition(
        component_id="people.person-name",
        contract_version=1,
        _schema_json=json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
    )
