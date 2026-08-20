import dataclasses

from src.db.models.competition_models import Form


@dataclasses.dataclass(frozen=True)
class FormDefinition:
    """Independently allocated resolved artifacts and metadata for one form version."""

    form_json_schema: dict
    form_ui_schema: list[dict]
    form_rule_schema: dict
    form_xml_transform_rules: dict
    form: Form
