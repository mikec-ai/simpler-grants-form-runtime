import dataclasses
from copy import deepcopy

from src.form_schema.shared import COMMON_SHARED_V1

_ORDINALS = (
    "First",
    "Second",
    "Third",
    "Fourth",
    "Fifth",
    "Sixth",
    "Seventh",
    "Eighth",
    "Ninth",
    "Tenth",
    "Eleventh",
    "Twelfth",
    "Thirteenth",
    "Fourteenth",
    "Fifteenth",
)


@dataclasses.dataclass(frozen=True)
class AttachmentSlotMetadata:
    """Analysis metadata for a runtime attachment slot, not an applicant question."""

    runtime_path: str
    component_id: str
    classification: str
    semantic_question_id: None
    ordinal: int


@dataclasses.dataclass(frozen=True)
class NumberedAttachmentSlots:
    """Independently allocated runtime artifacts for numbered attachment slots."""

    component_id: str
    json_schema_properties: dict[str, dict]
    ui_sections: list[dict]
    rule_schema: dict[str, dict]
    xml_attachment_fields: dict[str, dict]
    field_metadata: tuple[AttachmentSlotMetadata, ...]


def build_numbered_attachment_slots(count: int) -> NumberedAttachmentSlots:
    """Build the exact numbered-slot pattern demonstrated by Attachment Form."""

    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= len(_ORDINALS):
        raise ValueError(f"count must be an integer from 1 through {len(_ORDINALS)}")

    properties: dict[str, dict] = {}
    sections: list[dict] = []
    rules: dict[str, dict] = {}
    xml_fields: dict[str, dict] = {}
    metadata: list[AttachmentSlotMetadata] = []
    component_id = "application.numbered-attachment-slots"

    for ordinal in range(1, count + 1):
        field = f"att{ordinal}"
        properties[field] = {
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("attachment")}],
            "title": f"Attachment {ordinal}",
            "description": f"{_ORDINALS[ordinal - 1]} attachment file",
        }
        sections.append(
            {
                "type": "section",
                "label": f"{ordinal}) Attachment {ordinal}",
                "name": f"attachment{ordinal}",
                "children": [
                    {
                        "type": "field",
                        "definition": f"/properties/{field}",
                        "widget": "Attachment",
                    }
                ],
            }
        )
        rules[field] = {"gg_validation": {"rule": "attachment"}}
        xml_fields[field] = {
            "xml_element": f"ATT{ordinal}",
            "type": "single_with_wrapper",
        }
        metadata.append(
            AttachmentSlotMetadata(
                runtime_path=f"/{field}",
                component_id=component_id,
                classification="attachment",
                semantic_question_id=None,
                ordinal=ordinal,
            )
        )

    return NumberedAttachmentSlots(
        component_id=component_id,
        json_schema_properties=deepcopy(properties),
        ui_sections=deepcopy(sections),
        rule_schema=deepcopy(rules),
        xml_attachment_fields=deepcopy(xml_fields),
        field_metadata=tuple(metadata),
    )
