import importlib

from src.form_schema.forms.rr_budget10.config import FORM_ID, SHORT_FORM_NAME

_form_json = importlib.import_module("src.form_schema.forms.rr_budget10.1.0.form_json")
RRBudget10_v3_0 = _form_json.RRBudget10_v3_0

__all__ = ["FORM_ID", "SHORT_FORM_NAME", "RRBudget10_v3_0"]
