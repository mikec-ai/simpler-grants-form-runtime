import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import BudgetFamilyConfig, build_budget_family_form
from src.form_schema.forms.rr_mp_subaward_budget.config import FORM_ID, SHORT_FORM_NAME

_BUILD = build_budget_family_form(
    Path(__file__).with_name("draft_package"),
    BudgetFamilyConfig(
        source_form_id="RRMPSubawardBudget",
        form_id=FORM_ID,
        form_name="[Draft] Research & Related Multi-Project Subaward Budget Attachment(s) Form",
        short_form_name=SHORT_FORM_NAME,
        form_version="3.0",
        form_type=FormType.RR_MP_SUBAWARD_BUDGET,
        form_instruction_id=uuid.UUID("df810177-8f07-4496-9946-8a247f70d519"),
        budget_periods=10,
        subaward_items=30,
        technical_slots=30,
        embedded_budget_key="rr_mp_budget_3_0",
        source_nodes=231,
        countable_questions=187,
        repeating_groups=6,
        source_calculations=0,
        executable_sums=0,
    ),
)

RRMPSubawardBudget_v3_0 = _BUILD.form
FORM_JSON_SCHEMA = RRMPSubawardBudget_v3_0.form_json_schema
FORM_UI_SCHEMA = RRMPSubawardBudget_v3_0.form_ui_schema
FORM_RULE_SCHEMA = RRMPSubawardBudget_v3_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = RRMPSubawardBudget_v3_0.json_to_xml_schema
