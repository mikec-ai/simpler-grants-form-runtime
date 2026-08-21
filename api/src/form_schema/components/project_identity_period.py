import dataclasses

from src.form_schema.components.component_definition import (
    ComponentDefinition,
    ComponentDefinitionError,
    FieldContribution,
)


@dataclasses.dataclass(frozen=True)
class ProjectIdentityPeriodComponentConfig:
    """Exact presentation delta for the shared SF-424 project period fields."""

    date_description: str


def _field(
    *,
    field_key: str,
    title: str,
    description: str,
    schema: dict,
    xml_target: str,
) -> tuple[str, FieldContribution]:
    return (
        field_key,
        FieldContribution.create(
            schema={
                "type": "string",
                "title": title,
                "description": description,
                **schema,
            },
            ui={"type": "field", "definition": f"/properties/{field_key}"},
            direct_xml={"xml_transform": {"target": xml_target}},
        ),
    )


def build_project_identity_period_component(
    config: ProjectIdentityPeriodComponentConfig,
) -> ComponentDefinition:
    """Build the exact title and date fields shared by SF-424 and SF-424 Short."""

    if not isinstance(config.date_description, str) or not config.date_description.strip():
        raise ComponentDefinitionError("date_description must be a nonempty string")

    return ComponentDefinition(
        component_id="application.project-identity-period",
        contract_version=1,
        fields=(
            _field(
                field_key="project_title",
                title="Project Title",
                description="Enter a brief, descriptive title of the project.",
                schema={"minLength": 1, "maxLength": 200},
                xml_target="ProjectTitle",
            ),
            _field(
                field_key="project_start_date",
                title="Project Start Date",
                description=config.date_description,
                schema={"format": "date"},
                xml_target="ProjectStartDate",
            ),
            _field(
                field_key="project_end_date",
                title="Project End Date",
                description=config.date_description,
                schema={"format": "date"},
                xml_target="ProjectEndDate",
            ),
        ),
    )
