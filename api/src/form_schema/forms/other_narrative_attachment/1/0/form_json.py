import uuid

from src.constants.lookup_constants import FormType
from src.form_schema.families import (
    NarrativeAttachmentFamilyConfig,
    build_narrative_attachment_form,
)
from src.form_schema.forms.other_narrative_attachment.config import FORM_ID, SHORT_FORM_NAME

# Sources:
# https://grants.gov/forms/form-items-description/fid/542
# https://apply07.grants.gov/apply/forms/schemas/OtherNarrativeAttachments_1_2-V1.2.xsd
_definition = build_narrative_attachment_form(
    NarrativeAttachmentFamilyConfig(
        form_id=FORM_ID,
        legacy_form_id=542,
        form_name="Other Narrative Attachments",
        short_form_name=SHORT_FORM_NAME,
        form_version="1.2",
        form_instruction_id=uuid.UUID("63a8c6da-faf0-4634-8034-af4f0ce3ed08"),
        form_type=FormType.OTHER_NARRATIVE_ATTACHMENT,
        attachment_title="Other Narrative Files",
        section_label="1. Other Narrative File(s)",
        section_name="otherNarrativeFiles",
        xml_description="XML transformation rules for Other Narrative Attachments form",
        xml_form_name="OtherNarrativeAttachments_1_2",
        xml_namespace="http://apply.grants.gov/forms/OtherNarrativeAttachments_1_2-V1.2",
        xsd_url="https://apply07.grants.gov/apply/forms/schemas/OtherNarrativeAttachments_1_2-V1.2.xsd",
        global_namespace_order=("glob", "globLib"),
    )
)

FORM_JSON_SCHEMA = _definition.form_json_schema
FORM_UI_SCHEMA = _definition.form_ui_schema
FORM_RULE_SCHEMA = _definition.form_rule_schema
FORM_XML_TRANSFORM_RULES = _definition.form_xml_transform_rules
OtherNarrativeAttachment_v1_2 = _definition.form
del _definition
