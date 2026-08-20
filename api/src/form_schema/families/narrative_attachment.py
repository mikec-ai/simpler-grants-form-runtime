import dataclasses
import uuid

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form
from src.form_schema.families.form_definition import FormDefinition
from src.form_schema.shared import COMMON_SHARED_V1


@dataclasses.dataclass(frozen=True)
class NarrativeAttachmentFamilyConfig:
    """Exact per-form parameters for the narrative attachment family."""

    form_id: uuid.UUID
    legacy_form_id: int
    form_name: str
    short_form_name: str
    form_version: str
    form_instruction_id: uuid.UUID
    form_type: FormType
    attachment_title: str
    section_label: str
    section_name: str
    xml_description: str
    xml_form_name: str
    xml_namespace: str
    xsd_url: str
    global_namespace_order: tuple[str, str] = ("globLib", "glob")


def build_narrative_attachment_form(
    config: NarrativeAttachmentFamilyConfig,
) -> FormDefinition:
    """Build one narrative attachment form from shared behavior and explicit deltas."""

    form_json_schema = {
        "type": "object",
        "required": ["attachments"],
        "properties": {
            "attachments": {
                "type": "array",
                "title": config.attachment_title,
                "description": "At least one file must be attached",
                "minItems": 1,
                "maxItems": 100,
                "items": {"allOf": [{"$ref": COMMON_SHARED_V1.field_ref("attachment")}]},
            }
        },
    }

    form_ui_schema = [
        {
            "type": "section",
            "label": config.section_label,
            "name": config.section_name,
            "children": [
                {
                    "type": "field",
                    "definition": "/properties/attachments",
                    "widget": "AttachmentArray",
                }
            ],
        }
    ]

    form_rule_schema = {
        "attachments": {"gg_validation": {"rule": "attachment"}},
    }

    global_namespaces = {
        "glob": "http://apply.grants.gov/system/Global-V1.0",
        "globLib": "http://apply.grants.gov/system/GlobalLibrary-V2.0",
    }
    if set(config.global_namespace_order) != set(global_namespaces):
        raise ValueError("global_namespace_order must contain exactly 'glob' and 'globLib'")

    namespaces = {
        "default": config.xml_namespace,
        "att": "http://apply.grants.gov/system/Attachments-V1.0",
    }
    namespaces.update(
        {prefix: global_namespaces[prefix] for prefix in config.global_namespace_order}
    )

    form_xml_transform_rules = {
        "_xml_config": {
            "description": config.xml_description,
            "version": "1.0",
            "form_name": config.xml_form_name,
            "namespaces": namespaces,
            "xsd_url": config.xsd_url,
            "xml_structure": {
                "root_element": config.xml_form_name,
                "root_attributes": {"FormVersion": config.form_version},
            },
            "null_handling_options": {
                "exclude": "Default - exclude field entirely from XML (recommended)",
            },
            "attachment_fields": {
                "attachments": {
                    "xml_element": "Attachments",
                    "type": "multiple",
                },
            },
        }
    }

    form = Form(
        form_id=config.form_id,
        legacy_form_id=config.legacy_form_id,
        form_name=config.form_name,
        short_form_name=config.short_form_name,
        form_version=config.form_version,
        agency_code="SGG",
        omb_number=None,
        form_json_schema=form_json_schema,
        form_ui_schema=form_ui_schema,
        form_rule_schema=form_rule_schema,
        json_to_xml_schema=form_xml_transform_rules,
        form_instruction_id=config.form_instruction_id,
        form_type=config.form_type,
        sgg_version="1.0",
        is_deprecated=False,
    )

    return FormDefinition(
        form_json_schema=form_json_schema,
        form_ui_schema=form_ui_schema,
        form_rule_schema=form_rule_schema,
        form_xml_transform_rules=form_xml_transform_rules,
        form=form,
    )
