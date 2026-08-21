import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form

_PACKAGE_DIR = Path(__file__).with_name("draft_package")
_MANIFEST_PATH = _PACKAGE_DIR / "manifest.json"


def _load_verified_artifacts() -> dict[str, Any]:
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("contract") != "simpler-draft-form-package/v1":
        raise ValueError("Unsupported R&R SF-424 draft package contract")
    if manifest.get("review_boundary", {}).get("published_coverage_eligible") is not False:
        raise ValueError("The unreviewed R&R SF-424 draft cannot be coverage eligible")

    artifacts: dict[str, Any] = {}
    for artifact_name, expected_sha256 in manifest["artifacts"].items():
        artifact_path = _PACKAGE_DIR / artifact_name
        artifact_bytes = artifact_path.read_bytes()
        actual_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError(f"R&R SF-424 draft artifact hash mismatch: {artifact_name}")
        artifacts[artifact_name] = json.loads(artifact_bytes)
    return artifacts


_ARTIFACTS = _load_verified_artifacts()
FORM_JSON_SCHEMA = _ARTIFACTS["json-schema.json"]
FORM_UI_SCHEMA = _ARTIFACTS["ui-schema.json"]
FORM_RULE_SCHEMA = _ARTIFACTS["rule-schema.json"]
FORM_XML_TRANSFORM_RULES = _ARTIFACTS["xml-transform.json"]

RRSF424_v5_0 = Form(
    # Grants.gov source filename RR_SF424_5_0-V5.0_F768.xls.
    form_id=uuid.UUID("98f03cc4-5cd8-455b-a318-ba5abd0cf572"),
    legacy_form_id=768,
    form_name="[Draft] Research & Related Application for Federal Assistance (SF424 R&R)",
    short_form_name="RR_SF424_5_0",
    form_version="5.0",
    agency_code="SGG",
    form_json_schema=FORM_JSON_SCHEMA,
    form_ui_schema=FORM_UI_SCHEMA,
    form_rule_schema=FORM_RULE_SCHEMA,
    json_to_xml_schema=FORM_XML_TRANSFORM_RULES,
    form_type=FormType.RR_SF424,
    sgg_version="1.0-draft",
    is_deprecated=False,
)

del _ARTIFACTS
