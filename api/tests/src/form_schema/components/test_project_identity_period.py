import dataclasses

import pytest

from src.form_schema.components import (
    ComponentDefinitionError,
    ProjectIdentityPeriodComponentConfig,
    build_project_identity_period_component,
)


def _config() -> ProjectIdentityPeriodComponentConfig:
    return ProjectIdentityPeriodComponentConfig(
        date_description="Enter the date in the format MM/DD/YYYY. "
    )


def test_builds_project_identity_and_period_across_runtime_artifacts() -> None:
    component = build_project_identity_period_component(_config()).mount_root()

    assert component.json_schema_properties == {
        "project_title": {
            "type": "string",
            "title": "Project Title",
            "description": "Enter a brief, descriptive title of the project.",
            "minLength": 1,
            "maxLength": 200,
        },
        "project_start_date": {
            "type": "string",
            "title": "Project Start Date",
            "description": "Enter the date in the format MM/DD/YYYY. ",
            "format": "date",
        },
        "project_end_date": {
            "type": "string",
            "title": "Project End Date",
            "description": "Enter the date in the format MM/DD/YYYY. ",
            "format": "date",
        },
    }
    assert component.ui_schema_fields == {
        "project_title": {
            "type": "field",
            "definition": "/properties/project_title",
        },
        "project_start_date": {
            "type": "field",
            "definition": "/properties/project_start_date",
        },
        "project_end_date": {
            "type": "field",
            "definition": "/properties/project_end_date",
        },
    }
    assert component.rule_schema == {}
    assert component.xml_transform_rules == {
        "project_title": {"xml_transform": {"target": "ProjectTitle"}},
        "project_start_date": {"xml_transform": {"target": "ProjectStartDate"}},
        "project_end_date": {"xml_transform": {"target": "ProjectEndDate"}},
    }


def test_short_profile_changes_only_date_description() -> None:
    sf424 = build_project_identity_period_component(_config()).mount_root()
    short = build_project_identity_period_component(
        dataclasses.replace(_config(), date_description="Enter the date in the format MM/DD/YYYY.")
    ).mount_root()

    for field in ("project_start_date", "project_end_date"):
        assert short.json_schema_properties[field]["description"] == (
            "Enter the date in the format MM/DD/YYYY."
        )
    assert short.json_schema_properties["project_title"] == (
        sf424.json_schema_properties["project_title"]
    )
    assert short.ui_schema_fields == sf424.ui_schema_fields
    assert short.xml_transform_rules == sf424.xml_transform_rules


def test_rejects_empty_date_description() -> None:
    with pytest.raises(ComponentDefinitionError, match="must be a nonempty string"):
        build_project_identity_period_component(
            ProjectIdentityPeriodComponentConfig(date_description=" ")
        )
