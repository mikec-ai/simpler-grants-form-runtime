import dataclasses
import json
import re
from collections.abc import Collection, Mapping

_COMPONENT_ID = re.compile(r"^[a-z][a-z0-9.-]*$")
_FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_SOURCE_QUESTION_ID = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]*$")
_SUPPORTED_PREPOPULATION_RULES = frozenset(
    {
        "agency_name",
        "assistance_listing_number",
        "assistance_listing_program_title",
        "opportunity_number",
        "opportunity_title",
        "uei",
    }
)


class ComponentDefinitionError(ValueError):
    """Raised when a component contribution cannot be mounted safely."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclasses.dataclass(frozen=True)
class FieldContribution:
    """Immutable canonical contribution for one root-level form field."""

    _schema_json: str
    _ui_json: str
    _rule_json: str | None = None
    _direct_xml_json: str | None = None
    source_question_binding: str | None = None

    @classmethod
    def create(
        cls,
        *,
        schema: dict,
        ui: dict,
        rule: dict | None = None,
        direct_xml: dict | None = None,
        source_question_binding: str | None = None,
    ) -> FieldContribution:
        return cls(
            _schema_json=_canonical_json(schema),
            _ui_json=_canonical_json(ui),
            _rule_json=_canonical_json(rule) if rule is not None else None,
            _direct_xml_json=(_canonical_json(direct_xml) if direct_xml is not None else None),
            source_question_binding=source_question_binding,
        )

    def schema(self) -> dict:
        return json.loads(self._schema_json)

    def ui(self) -> dict:
        return json.loads(self._ui_json)

    def rule(self) -> dict | None:
        return json.loads(self._rule_json) if self._rule_json is not None else None

    def direct_xml(self) -> dict | None:
        if self._direct_xml_json is None:
            return None
        return json.loads(self._direct_xml_json)


@dataclasses.dataclass(frozen=True)
class MountedComponentDefinition:
    """Independently allocated root-field contributions ready for form placement."""

    component_id: str
    contract_version: int
    json_schema_properties: dict
    ui_schema_fields: dict[str, dict]
    rule_schema: dict
    xml_transform_rules: dict
    source_question_bindings: dict[str, str]


@dataclasses.dataclass(frozen=True)
class ComponentDefinition:
    """Validated question-granular component with restricted root mounting."""

    component_id: str
    contract_version: int
    fields: tuple[tuple[str, FieldContribution], ...]

    def __post_init__(self) -> None:
        if not _COMPONENT_ID.fullmatch(self.component_id):
            raise ComponentDefinitionError("component_id is invalid")
        if self.contract_version < 1:
            raise ComponentDefinitionError("contract_version must be positive")
        if not self.fields:
            raise ComponentDefinitionError("component must contribute at least one field")

        seen: set[str] = set()
        for field_key, contribution in self.fields:
            if not isinstance(contribution, FieldContribution):
                raise ComponentDefinitionError(f"{field_key} must use a FieldContribution")
            if not _FIELD_KEY.fullmatch(field_key):
                raise ComponentDefinitionError(f"invalid root field key: {field_key!r}")
            if field_key in seen:
                raise ComponentDefinitionError(f"duplicate component field: {field_key}")
            seen.add(field_key)

            schema = contribution.schema()
            if not schema:
                raise ComponentDefinitionError(f"{field_key} schema must not be empty")
            ui = contribution.ui()
            if set(ui) != {"type", "definition"}:
                raise ComponentDefinitionError(
                    f"{field_key} UI must contain only type and definition"
                )
            if ui.get("definition") != f"/properties/{field_key}":
                raise ComponentDefinitionError(
                    f"{field_key} UI definition must target its own root property"
                )
            if ui.get("type") not in {"field", "null"}:
                raise ComponentDefinitionError(f"{field_key} UI type must be 'field' or 'null'")

            rule = contribution.rule()
            if rule is not None:
                if set(rule) != {"gg_pre_population"}:
                    raise ComponentDefinitionError(
                        f"{field_key} rule contains unsupported behavior"
                    )
                prepopulation = rule.get("gg_pre_population")
                if (
                    not isinstance(prepopulation, dict)
                    or set(prepopulation) != {"rule"}
                    or prepopulation.get("rule") not in _SUPPORTED_PREPOPULATION_RULES
                ):
                    raise ComponentDefinitionError(
                        f"{field_key} rule contains unsupported behavior"
                    )

            direct_xml = contribution.direct_xml()
            if direct_xml is not None:
                if set(direct_xml) != {"xml_transform"}:
                    raise ComponentDefinitionError(
                        f"{field_key} direct XML must contain only xml_transform"
                    )
                transform = direct_xml.get("xml_transform")
                if not isinstance(transform, dict):
                    raise ComponentDefinitionError(
                        f"{field_key} direct XML target must be a nonempty string"
                    )
                target = transform.get("target")
                if not isinstance(target, str) or not target.strip():
                    raise ComponentDefinitionError(
                        f"{field_key} direct XML target must be a nonempty string"
                    )
                if set(transform) - {"target", "namespace"}:
                    raise ComponentDefinitionError(
                        f"{field_key} direct XML contains unsupported behavior"
                    )
                namespace = transform.get("namespace")
                if namespace is not None and (
                    not isinstance(namespace, str) or not namespace.strip()
                ):
                    raise ComponentDefinitionError(
                        f"{field_key} direct XML namespace must be a nonempty string"
                    )

            source_binding = contribution.source_question_binding
            if source_binding is not None and (
                not isinstance(source_binding, str)
                or not _SOURCE_QUESTION_ID.fullmatch(source_binding)
            ):
                raise ComponentDefinitionError(f"{field_key} source question binding is invalid")

    @property
    def field_keys(self) -> tuple[str, ...]:
        return tuple(field_key for field_key, _ in self.fields)

    def mount_root(
        self,
        *,
        aliases: Mapping[str, str] | None = None,
        reserved_fields: Collection[str] = (),
    ) -> MountedComponentDefinition:
        """Mount fields at the form root with optional, restricted key aliases."""

        alias_map = dict(aliases or {})
        unknown_aliases = set(alias_map) - set(self.field_keys)
        if unknown_aliases:
            raise ComponentDefinitionError(
                f"aliases contain unknown component fields: {sorted(unknown_aliases)}"
            )

        mounted_keys = {
            field_key: alias_map.get(field_key, field_key) for field_key in self.field_keys
        }
        for mounted_key in mounted_keys.values():
            if not _FIELD_KEY.fullmatch(mounted_key):
                raise ComponentDefinitionError(f"alias must be a root field key: {mounted_key!r}")
        if len(set(mounted_keys.values())) != len(mounted_keys):
            raise ComponentDefinitionError("aliases produce duplicate destination fields")
        collisions = set(mounted_keys.values()) & set(reserved_fields)
        if collisions:
            raise ComponentDefinitionError(
                f"component fields collide with reserved fields: {sorted(collisions)}"
            )

        properties: dict[str, dict] = {}
        ui_fields: dict[str, dict] = {}
        rules: dict[str, dict] = {}
        xml_rules: dict[str, dict] = {}
        source_bindings: dict[str, str] = {}
        for field_key, contribution in self.fields:
            mounted_key = mounted_keys[field_key]
            properties[mounted_key] = contribution.schema()
            ui = contribution.ui()
            ui["definition"] = f"/properties/{mounted_key}"
            ui_fields[mounted_key] = ui
            if (rule := contribution.rule()) is not None:
                rules[mounted_key] = rule
            if (direct_xml := contribution.direct_xml()) is not None:
                xml_rules[mounted_key] = direct_xml
            if contribution.source_question_binding is not None:
                source_bindings[mounted_key] = contribution.source_question_binding

        return MountedComponentDefinition(
            component_id=self.component_id,
            contract_version=self.contract_version,
            json_schema_properties=properties,
            ui_schema_fields=ui_fields,
            rule_schema=rules,
            xml_transform_rules=xml_rules,
            source_question_bindings=source_bindings,
        )
