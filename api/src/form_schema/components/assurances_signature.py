import dataclasses

from src.form_schema.components.component_definition import ComponentDefinition, FieldContribution
from src.form_schema.components.organization_identity import (
    OrganizationNameComponentConfig,
    build_organization_name_component,
)
from src.form_schema.shared import COMMON_SHARED_V1


@dataclasses.dataclass(frozen=True)
class AssurancesSignatureComponentConfig:
    """Exact presentation delta shared by the SF-424B and SF-424D profiles."""

    date_title: str


def build_assurances_signature_component(
    config: AssurancesSignatureComponentConfig,
) -> ComponentDefinition:
    organization = build_organization_name_component(
        OrganizationNameComponentConfig(
            title="Applicant Organization",
            description="This should match the 'Legal Name' field from the SF-424 form",
        )
    ).mount_root(aliases={"organization_name": "applicant_organization"})

    return ComponentDefinition(
        component_id="application.assurances-signature",
        contract_version=1,
        fields=(
            (
                "signature",
                FieldContribution.create(
                    schema={
                        "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("signature")}],
                        "title": "Signature of the Authorized Certifying Official",
                        "description": "Completed by Grants.gov upon submission.",
                    },
                    ui={"type": "null", "definition": "/properties/signature"},
                ),
            ),
            (
                "title",
                FieldContribution.create(
                    schema={
                        "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("contact_person_title")}],
                        "description": "This should match the 'Authorized Representative Title' field from the SF-424 form",
                    },
                    ui={"type": "field", "definition": "/properties/title"},
                ),
            ),
            (
                "applicant_organization",
                FieldContribution.create(
                    schema=organization.json_schema_properties["applicant_organization"],
                    ui=organization.ui_schema_fields["applicant_organization"],
                ),
            ),
            (
                "date_signed",
                FieldContribution.create(
                    schema={
                        "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("submitted_date")}],
                        "title": config.date_title,
                    },
                    ui={"type": "null", "definition": "/properties/date_signed"},
                ),
            ),
        ),
    )
