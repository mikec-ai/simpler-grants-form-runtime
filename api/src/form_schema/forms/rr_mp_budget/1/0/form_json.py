import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import BudgetFamilyConfig, build_budget_family_form
from src.form_schema.forms.rr_mp_budget.config import FORM_ID, SHORT_FORM_NAME

_BUILD = build_budget_family_form(
    Path(__file__).with_name("draft_package"),
    BudgetFamilyConfig(
        source_form_id="RRMPBudget",
        form_id=FORM_ID,
        form_name="[Draft] Research & Related Multi-Project Budget Form",
        short_form_name=SHORT_FORM_NAME,
        form_version="3.0",
        form_type=FormType.RR_MP_BUDGET,
        form_instruction_id=uuid.UUID("f1bfa235-b36e-4b00-bc8b-ea9bb0a970e4"),
        budget_periods=10,
        countable_questions=157,
        executable_sums=10,
    ),
)

RRMPBudget_v3_0 = _BUILD.form
FORM_JSON_SCHEMA = RRMPBudget_v3_0.form_json_schema
FORM_UI_SCHEMA = RRMPBudget_v3_0.form_ui_schema
FORM_RULE_SCHEMA = RRMPBudget_v3_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = RRMPBudget_v3_0.json_to_xml_schema
