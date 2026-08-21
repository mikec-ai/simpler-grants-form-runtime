import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import BudgetFamilyConfig, build_budget_family_form
from src.form_schema.forms.rr_budget.config import FORM_ID, SHORT_FORM_NAME

_BUILD = build_budget_family_form(
    Path(__file__).with_name("draft_package"),
    BudgetFamilyConfig(
        source_form_id="RRBudget",
        form_id=FORM_ID,
        form_name="[Draft] Research & Related Budget",
        short_form_name=SHORT_FORM_NAME,
        form_version="3.0",
        form_type=FormType.RR_BUDGET,
        form_instruction_id=uuid.UUID("6c604b81-8582-4d39-b899-f3e15bbcd3ef"),
        budget_periods=5,
        countable_questions=97,
    ),
)

RRBudget_v3_0 = _BUILD.form
FORM_JSON_SCHEMA = RRBudget_v3_0.form_json_schema
FORM_UI_SCHEMA = RRBudget_v3_0.form_ui_schema
FORM_RULE_SCHEMA = RRBudget_v3_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = RRBudget_v3_0.json_to_xml_schema
