import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import BudgetFamilyConfig, build_budget_family_form
from src.form_schema.forms.rr_subaward_budget10_30.config import FORM_ID, SHORT_FORM_NAME

_BUILD = build_budget_family_form(
    Path(__file__).with_name("draft_package"),
    BudgetFamilyConfig(
        source_form_id="RRSubawardBudget10_30",
        form_id=FORM_ID,
        form_name="[Draft] R&R Subaward Budget Attachment(s) Form 10 YR 30 ATT",
        short_form_name=SHORT_FORM_NAME,
        form_version="3.0",
        form_type=FormType.RR_SUBAWARD_BUDGET_10_30,
        form_instruction_id=uuid.UUID("f75a27cd-770b-41e9-bca8-ef0097201852"),
        budget_periods=10,
        subaward_items=30,
        technical_slots=30,
        embedded_budget_key="rr_budget_10_3_0",
        source_nodes=231,
        countable_questions=142,
        repeating_groups=6,
    ),
)

RRSubawardBudget10_30_v3_0 = _BUILD.form
FORM_JSON_SCHEMA = RRSubawardBudget10_30_v3_0.form_json_schema
FORM_UI_SCHEMA = RRSubawardBudget10_30_v3_0.form_ui_schema
FORM_RULE_SCHEMA = RRSubawardBudget10_30_v3_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = RRSubawardBudget10_30_v3_0.json_to_xml_schema
