import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import BudgetFamilyConfig, build_budget_family_form
from src.form_schema.forms.rr_budget10.config import FORM_ID, SHORT_FORM_NAME

_BUILD = build_budget_family_form(
    Path(__file__).with_name("draft_package"),
    BudgetFamilyConfig(
        source_form_id="RRBudget10",
        form_id=FORM_ID,
        form_name="[Draft] Research & Related Budget 10YR",
        short_form_name=SHORT_FORM_NAME,
        form_version="3.0",
        form_type=FormType.RR_BUDGET_10,
        form_instruction_id=uuid.UUID("6436c11c-0756-4806-885f-819d21ffe914"),
        budget_periods=10,
        countable_questions=107,
    ),
)

RRBudget10_v3_0 = _BUILD.form
FORM_JSON_SCHEMA = RRBudget10_v3_0.form_json_schema
FORM_UI_SCHEMA = RRBudget10_v3_0.form_ui_schema
FORM_RULE_SCHEMA = RRBudget10_v3_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = RRBudget10_v3_0.json_to_xml_schema
