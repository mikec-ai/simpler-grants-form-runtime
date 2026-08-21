import importlib

from src.form_schema.forms.phs_fellowship_supplemental.config import FORM_ID, SHORT_FORM_NAME

_form_json = importlib.import_module(
    "src.form_schema.forms.phs_fellowship_supplemental.1.0.form_json"
)
PHSFellowshipSupplemental_v8_0 = _form_json.PHSFellowshipSupplemental_v8_0

__all__ = ["FORM_ID", "SHORT_FORM_NAME", "PHSFellowshipSupplemental_v8_0"]
