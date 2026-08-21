import importlib

from src.form_schema.forms.rr_mp_budget.config import FORM_ID, SHORT_FORM_NAME

_form_json = importlib.import_module("src.form_schema.forms.rr_mp_budget.1.0.form_json")
RRMPBudget_v3_0 = _form_json.RRMPBudget_v3_0

__all__ = ["FORM_ID", "SHORT_FORM_NAME", "RRMPBudget_v3_0"]
