import uuid
from pathlib import Path

from src.constants.lookup_constants import FormType
from src.form_schema.components.source_resolved_form import (
    SourceResolvedFormConfig,
    build_source_resolved_form,
)
from src.form_schema.forms.phs_fellowship_supplemental.config import FORM_ID, SHORT_FORM_NAME

_BUILD = build_source_resolved_form(
    Path(__file__).with_name("draft_package"),
    SourceResolvedFormConfig(
        source_form_id="PHSFellowshipSupplemental",
        form_id=FORM_ID,
        form_name="[Draft] PHS Fellowship Supplemental Form",
        short_form_name=SHORT_FORM_NAME,
        form_version="8.0",
        form_type=FormType.PHS_FELLOWSHIP_SUPPLEMENTAL,
        form_instruction_id=uuid.UUID("5374a4b4-6706-434f-ac38-173581219b4e"),
        source_nodes=165,
        conditions=43,
        calculations=2,
        attachment_fields=17,
        unsupported_scalar_arrays=(
            "PHS_Fellowship_Supplemental_8_0.AdditionalInformation.StemCells.CellLines",
        ),
    ),
)

PHSFellowshipSupplemental_v8_0 = _BUILD.form
FORM_JSON_SCHEMA = PHSFellowshipSupplemental_v8_0.form_json_schema
FORM_UI_SCHEMA = PHSFellowshipSupplemental_v8_0.form_ui_schema
FORM_RULE_SCHEMA = PHSFellowshipSupplemental_v8_0.form_rule_schema
FORM_XML_TRANSFORM_RULES = PHSFellowshipSupplemental_v8_0.json_to_xml_schema
