import dataclasses
import uuid

import pytest

from src.constants.lookup_constants import FormType
from src.form_schema.forms.budget_narrative_attachment import BudgetNarrativeAttachment_v1_2
from src.form_schema.forms.other_narrative_attachment import OtherNarrativeAttachment_v1_2
from src.form_schema.forms.project_narrative_attachment import ProjectNarrativeAttachment_v1_2
from src.form_schema.templates import (
    NarrativeAttachmentTemplateConfig,
    build_narrative_attachment_form,
)


def _config(**overrides) -> NarrativeAttachmentTemplateConfig:
    values = {
        "form_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "legacy_form_id": 123,
        "form_name": "Example Narrative Attachments",
        "short_form_name": "ExampleNarrativeAttachments_1_2",
        "form_version": "1.2",
        "form_instruction_id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
        "form_type": FormType.ATTACHMENT_FORM,
        "attachment_title": "Example Narrative Files",
        "section_label": "1. Example Narrative File(s)",
        "section_name": "exampleNarrativeFiles",
        "xml_description": "XML transformation rules for Example Narrative Attachments form",
        "xml_form_name": "ExampleNarrativeAttachments_1_2",
        "xml_namespace": "https://example.gov/forms/ExampleNarrativeAttachments_1_2-V1.2",
        "xsd_url": "https://example.gov/schemas/ExampleNarrativeAttachments_1_2-V1.2.xsd",
    }
    values.update(overrides)
    return NarrativeAttachmentTemplateConfig(**values)


def test_builds_all_runtime_artifacts_from_explicit_parameters() -> None:
    definition = build_narrative_attachment_form(_config())

    attachment_schema = definition.form_json_schema["properties"]["attachments"]
    assert attachment_schema["title"] == "Example Narrative Files"
    assert attachment_schema["minItems"] == 1
    assert attachment_schema["maxItems"] == 100
    assert definition.form_ui_schema[0]["name"] == "exampleNarrativeFiles"
    assert definition.form_rule_schema == {"attachments": {"gg_validation": {"rule": "attachment"}}}

    xml_config = definition.form_xml_transform_rules["_xml_config"]
    assert xml_config["form_name"] == "ExampleNarrativeAttachments_1_2"
    assert xml_config["xsd_url"].endswith("ExampleNarrativeAttachments_1_2-V1.2.xsd")
    assert xml_config["xml_structure"]["root_attributes"] == {"FormVersion": "1.2"}

    assert definition.form.form_json_schema is definition.form_json_schema
    assert definition.form.form_ui_schema is definition.form_ui_schema
    assert definition.form.form_rule_schema is definition.form_rule_schema
    assert definition.form.json_to_xml_schema is definition.form_xml_transform_rules


def test_builds_independent_form_artifacts() -> None:
    first = build_narrative_attachment_form(_config())
    second = build_narrative_attachment_form(
        dataclasses.replace(
            _config(),
            form_id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
            attachment_title="Second Narrative Files",
        )
    )

    first.form_json_schema["properties"]["attachments"]["title"] = "Changed"

    assert second.form_json_schema["properties"]["attachments"]["title"] == (
        "Second Narrative Files"
    )


def test_rejects_incomplete_global_namespace_order() -> None:
    with pytest.raises(ValueError, match="exactly 'glob' and 'globLib'"):
        build_narrative_attachment_form(
            dataclasses.replace(_config(), global_namespace_order=("glob", "glob"))
        )


@pytest.mark.parametrize(
    (
        "form",
        "form_id",
        "legacy_form_id",
        "form_name",
        "short_form_name",
        "form_instruction_id",
        "form_type",
        "attachment_title",
        "section_label",
        "section_name",
        "xml_form_name",
        "xml_namespace",
        "xsd_url",
        "xml_description",
        "namespace_order",
    ),
    [
        (
            ProjectNarrativeAttachment_v1_2,
            uuid.UUID("32165da2-354d-42c0-a986-cf4f2f350039"),
            539,
            "Project Narrative Attachment Form",
            "ProjectNarrativeAttachments_1_2",
            uuid.UUID("be89e8c1-06d2-4a81-b157-41c1a5db5acf"),
            FormType.PROJECT_NARRATIVE_ATTACHMENT,
            "Project Narrative Files",
            "1. Project Narrative File(s)",
            "projectNarrativeFiles",
            "ProjectNarrativeAttachments_1_2",
            "http://apply.grants.gov/forms/ProjectNarrativeAttachments_1_2-V1.2",
            "https://apply07.grants.gov/apply/forms/schemas/ProjectNarrativeAttachments_1_2-V1.2.xsd",
            "XML transformation rules for Project Narrative Attachments form",
            ["default", "att", "globLib", "glob"],
        ),
        (
            OtherNarrativeAttachment_v1_2,
            uuid.UUID("8899954c-2919-4398-96aa-73961179fe16"),
            542,
            "Other Narrative Attachments",
            "OtherNarrativeAttachments",
            uuid.UUID("63a8c6da-faf0-4634-8034-af4f0ce3ed08"),
            FormType.OTHER_NARRATIVE_ATTACHMENT,
            "Other Narrative Files",
            "1. Other Narrative File(s)",
            "otherNarrativeFiles",
            "OtherNarrativeAttachments_1_2",
            "http://apply.grants.gov/forms/OtherNarrativeAttachments_1_2-V1.2",
            "https://apply07.grants.gov/apply/forms/schemas/OtherNarrativeAttachments_1_2-V1.2.xsd",
            "XML transformation rules for Other Narrative Attachments form",
            ["default", "att", "glob", "globLib"],
        ),
        (
            BudgetNarrativeAttachment_v1_2,
            uuid.UUID("66092260-d3c2-4427-8fd2-bb14e1590aff"),
            543,
            "Budget Narrative Attachment Form",
            "BudgetNarrativeAttachments_1_2",
            uuid.UUID("2bf892d2-dbba-4126-a71c-b4b8ea2f2908"),
            FormType.BUDGET_NARRATIVE_ATTACHMENT,
            "Budget Narrative Files",
            "1. Budget Narrative File(s)",
            "budgetNarrativeFiles",
            "BudgetNarrativeAttachments_1_2",
            "http://apply.grants.gov/forms/BudgetNarrativeAttachments_1_2-V1.2",
            "https://apply07.grants.gov/apply/forms/schemas/BudgetNarrativeAttachments_1_2-V1.2.xsd",
            "XML transformation rules for Budget Narrative Attachments form",
            ["default", "att", "globLib", "glob"],
        ),
    ],
)
def test_supported_variants_preserve_exact_form_and_wire_deltas(
    form,
    form_id,
    legacy_form_id,
    form_name,
    short_form_name,
    form_instruction_id,
    form_type,
    attachment_title,
    section_label,
    section_name,
    xml_form_name,
    xml_namespace,
    xsd_url,
    xml_description,
    namespace_order,
) -> None:
    assert form.form_id == form_id
    assert form.legacy_form_id == legacy_form_id
    assert form.form_name == form_name
    assert form.short_form_name == short_form_name
    assert form.form_instruction_id == form_instruction_id
    assert form.form_type == form_type
    assert form.form_version == "1.2"
    assert form.form_json_schema["properties"]["attachments"]["title"] == attachment_title
    assert form.form_ui_schema == [
        {
            "type": "section",
            "label": section_label,
            "name": section_name,
            "children": [
                {
                    "type": "field",
                    "definition": "/properties/attachments",
                    "widget": "AttachmentArray",
                }
            ],
        }
    ]
    assert form.form_rule_schema == {"attachments": {"gg_validation": {"rule": "attachment"}}}

    xml_config = form.json_to_xml_schema["_xml_config"]
    assert xml_config["form_name"] == xml_form_name
    assert xml_config["namespaces"]["default"] == xml_namespace
    assert list(xml_config["namespaces"]) == namespace_order
    assert xml_config["xsd_url"] == xsd_url
    assert xml_config["description"] == xml_description
    assert xml_config["xml_structure"] == {
        "root_element": xml_form_name,
        "root_attributes": {"FormVersion": "1.2"},
    }
