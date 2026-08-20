import uuid

from src.constants.lookup_constants import FormType
from src.form_schema.forms.budget_narrative_attachment.config import FORM_ID, SHORT_FORM_NAME
from src.form_schema.templates import (
    NarrativeAttachmentTemplateConfig,
    build_narrative_attachment_form,
)

# Sources:
# https://grants.gov/forms/form-items-description/fid/543
# https://apply07.grants.gov/apply/forms/schemas/BudgetNarrativeAttachments_1_2-V1.2.xsd
_definition = build_narrative_attachment_form(
    NarrativeAttachmentTemplateConfig(
        form_id=FORM_ID,
        legacy_form_id=543,
        form_name="Budget Narrative Attachment Form",
        short_form_name=SHORT_FORM_NAME,
        form_version="1.2",
        form_instruction_id=uuid.UUID("2bf892d2-dbba-4126-a71c-b4b8ea2f2908"),
        form_type=FormType.BUDGET_NARRATIVE_ATTACHMENT,
        attachment_title="Budget Narrative Files",
        section_label="1. Budget Narrative File(s)",
        section_name="budgetNarrativeFiles",
        xml_description="XML transformation rules for Budget Narrative Attachments form",
        xml_form_name="BudgetNarrativeAttachments_1_2",
        xml_namespace="http://apply.grants.gov/forms/BudgetNarrativeAttachments_1_2-V1.2",
        xsd_url="https://apply07.grants.gov/apply/forms/schemas/BudgetNarrativeAttachments_1_2-V1.2.xsd",
    )
)

FORM_JSON_SCHEMA = _definition.form_json_schema
FORM_UI_SCHEMA = _definition.form_ui_schema
FORM_RULE_SCHEMA = _definition.form_rule_schema
FORM_XML_TRANSFORM_RULES = _definition.form_xml_transform_rules
BudgetNarrativeAttachment_v1_2 = _definition.form
del _definition
