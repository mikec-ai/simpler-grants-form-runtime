import importlib

from src.form_schema.forms.rr_subaward_budget30.config import FORM_ID, SHORT_FORM_NAME

_form_json = importlib.import_module("src.form_schema.forms.rr_subaward_budget30.1.0.form_json")
RRSubawardBudget30_v3_0 = _form_json.RRSubawardBudget30_v3_0

__all__ = ["FORM_ID", "SHORT_FORM_NAME", "RRSubawardBudget30_v3_0"]
