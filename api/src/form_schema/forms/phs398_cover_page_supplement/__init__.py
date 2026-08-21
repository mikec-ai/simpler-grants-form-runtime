import importlib

from src.form_schema.forms.phs398_cover_page_supplement.config import FORM_ID, SHORT_FORM_NAME

_form_json = importlib.import_module(
    "src.form_schema.forms.phs398_cover_page_supplement.1.0.form_json"
)
PHS398CoverPageSupplement_v5_0 = _form_json.PHS398CoverPageSupplement_v5_0

__all__ = ["FORM_ID", "SHORT_FORM_NAME", "PHS398CoverPageSupplement_v5_0"]
