import json
import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.source_resolved_form import (
    SourceResolvedFormConfig,
    build_source_resolved_form,
)
from src.form_schema.forms.phs398_cover_page_supplement.config import FORM_ID, SHORT_FORM_NAME
from src.form_schema.forms.phs398_cover_page_supplement.presentation import apply_pdf_presentation
from src.form_schema.xml_plan import compile_xml_plan

_PACKAGE_DIR = Path(__file__).with_name("draft_package")

_BUILD = build_source_resolved_form(
    _PACKAGE_DIR,
    SourceResolvedFormConfig(
        source_form_id="PHS398CoverPageSupplement",
        form_id=FORM_ID,
        form_name="[Draft] PHS 398 Cover Page Supplement",
        short_form_name=SHORT_FORM_NAME,
        form_version="5.0",
        form_type=FormType.PHS398_COVER_PAGE_SUPPLEMENT,
        form_instruction_id=uuid.UUID("48556dc9-f742-59cc-8d9b-28e82abca070"),
        source_nodes=38,
        conditions=22,
        calculations=0,
        attachment_fields=2,
        unsupported_scalar_arrays=("PHS398_CoverPageSupplement_5_0.StemCells.CellLines",),
    ),
)

PHS398CoverPageSupplement_v5_0 = _BUILD.form
PHS398CoverPageSupplement_v5_0.form_ui_schema = apply_pdf_presentation(
    PHS398CoverPageSupplement_v5_0.form_ui_schema
)
PHS398CoverPageSupplement_v5_0.json_to_xml_schema = compile_xml_plan(
    json.loads((_PACKAGE_DIR / "xml-plan.json").read_text(encoding="utf-8")),
    source_root=_PACKAGE_DIR,
    source_manifest=json.loads(
        (_PACKAGE_DIR / "xml-source-manifest.json").read_text(encoding="utf-8")
    ),
)
FORM_JSON_SCHEMA = PHS398CoverPageSupplement_v5_0.form_json_schema
FORM_UI_SCHEMA = PHS398CoverPageSupplement_v5_0.form_ui_schema
FORM_RULE_SCHEMA = PHS398CoverPageSupplement_v5_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = PHS398CoverPageSupplement_v5_0.json_to_xml_schema
