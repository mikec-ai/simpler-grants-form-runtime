import uuid

from src.constants.lookup_constants import FormType
from src.form_schema.forms.project_narrative_attachment.config import FORM_ID, SHORT_FORM_NAME
from src.form_schema.templates import (
    NarrativeAttachmentTemplateConfig,
    build_narrative_attachment_form,
)

# Sources:
# https://grants.gov/forms/form-items-description/fid/539
# https://apply07.grants.gov/apply/forms/schemas/ProjectNarrativeAttachments_1_2-V1.2.xsd
_definition = build_narrative_attachment_form(
    NarrativeAttachmentTemplateConfig(
        form_id=FORM_ID,
        legacy_form_id=539,
        form_name="Project Narrative Attachment Form",
        short_form_name=SHORT_FORM_NAME,
        form_version="1.2",
        form_instruction_id=uuid.UUID("be89e8c1-06d2-4a81-b157-41c1a5db5acf"),
        form_type=FormType.PROJECT_NARRATIVE_ATTACHMENT,
        attachment_title="Project Narrative Files",
        section_label="1. Project Narrative File(s)",
        section_name="projectNarrativeFiles",
        xml_description="XML transformation rules for Project Narrative Attachments form",
        xml_form_name="ProjectNarrativeAttachments_1_2",
        xml_namespace="http://apply.grants.gov/forms/ProjectNarrativeAttachments_1_2-V1.2",
        xsd_url="https://apply07.grants.gov/apply/forms/schemas/ProjectNarrativeAttachments_1_2-V1.2.xsd",
    )
)

FORM_JSON_SCHEMA = _definition.form_json_schema
FORM_UI_SCHEMA = _definition.form_ui_schema
FORM_RULE_SCHEMA = _definition.form_rule_schema
FORM_XML_TRANSFORM_RULES = _definition.form_xml_transform_rules
ProjectNarrativeAttachment_v1_2 = _definition.form
del _definition
