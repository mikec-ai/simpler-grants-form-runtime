"""Tests for json_rule_validator, focusing on attachment ID collection."""

import uuid
from types import SimpleNamespace

import pytest

from src.form_schema.rule_processing.json_rule_context import (
    JsonRule,
    JsonRuleConfig,
    JsonRuleContext,
)
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context
from src.form_schema.rule_processing.json_rule_validator import (
    VALIDATION_RULES,
    validate_date_not_before,
)
from src.validation.validation_constants import ValidationErrorType
from tests.src.form_schema.rule_processing.conftest import setup_context


def _date_context(data: dict) -> SimpleNamespace:
    return SimpleNamespace(json_data=data, validation_issues=[])


def test_date_not_before_accepts_equal_and_later_dates() -> None:
    rule = JsonRule(
        handler="gg_validation",
        rule={"rule": "date_not_before", "other_field": "period.start"},
        path=["period", "end"],
    )
    for end_date in ("2026-08-21", "2026-08-22"):
        context = _date_context({"period": {"start": "2026-08-21", "end": end_date}})
        validate_date_not_before(context, rule)
        assert context.validation_issues == []


def test_date_not_before_reports_target_path_and_value() -> None:
    context = _date_context({"period": {"start": "2026-08-21", "end": "2026-08-20"}})
    rule = JsonRule(
        handler="gg_validation",
        rule={"rule": "date_not_before", "other_field": "period.start"},
        path=["period", "end"],
    )

    validate_date_not_before(context, rule)

    assert len(context.validation_issues) == 1
    issue = context.validation_issues[0]
    assert issue.type == ValidationErrorType.INVALID_DATE_ORDER
    assert issue.field == "$.period.end"
    assert issue.value == "2026-08-20"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"period": {"start": "not-a-date", "end": "2026-08-20"}},
        {"period": {"start": "2026-08-21", "end": "not-a-date"}},
    ],
)
def test_date_not_before_defers_missing_and_invalid_dates_to_json_schema(data: dict) -> None:
    context = _date_context(data)
    validate_date_not_before(
        context,
        JsonRule(
            handler="gg_validation",
            rule={"rule": "date_not_before", "other_field": "period.start"},
            path=["period", "end"],
        ),
    )
    assert context.validation_issues == []


@pytest.mark.parametrize(
    "rule",
    [
        {"rule": "date_not_before"},
        {"rule": "date_not_before", "other_field": ""},
        {"rule": "date_not_before", "other_field": "$.period.start"},
        {"rule": "date_not_before", "other_field": "period.start", "message": "custom"},
    ],
)
def test_date_not_before_rejects_invalid_contracts(rule: dict) -> None:
    with pytest.raises(ValueError):
        validate_date_not_before(
            _date_context({}),
            JsonRule(handler="gg_validation", rule=rule, path=["period", "end"]),
        )


def test_date_not_before_is_registered() -> None:
    assert VALIDATION_RULES["date_not_before"] is validate_date_not_before


def test_date_not_before_runs_through_rule_processor_without_database() -> None:
    application_form = SimpleNamespace(
        application_form_id="test-form",
        form_id="RRSF424",
        application_response={
            "period": {"start": "2026-08-21", "end": "2026-08-20"},
        },
        form=SimpleNamespace(
            form_rule_schema={
                "period": {
                    "end": {
                        "gg_validation": {
                            "rule": "date_not_before",
                            "other_field": "period.start",
                        }
                    }
                }
            }
        ),
    )
    context = JsonRuleContext(application_form, JsonRuleConfig())

    process_rule_schema_for_context(context)

    assert [issue.type for issue in context.validation_issues] == [
        ValidationErrorType.INVALID_DATE_ORDER
    ]


class TestAttachmentIdCollection:
    def test_valid_attachment_id_collected(self, enable_factory_create):
        att_id = str(uuid.uuid4())
        context = setup_context(
            {"att_field": att_id},
            rule_schema={"att_field": {"gg_validation": {"rule": "attachment"}}},
            attachment_ids=[att_id],
        )
        process_rule_schema_for_context(context)
        assert att_id in context.attachment_ids

    def test_invalid_attachment_id_still_collected(self, enable_factory_create):
        """An ID not on the application is still added to attachment_ids (validation adds an error,
        but collection is unconditional)."""
        att_id = str(uuid.uuid4())
        context = setup_context(
            {"att_field": att_id},
            rule_schema={"att_field": {"gg_validation": {"rule": "attachment"}}},
            attachment_ids=[],
        )
        process_rule_schema_for_context(context)
        assert att_id in context.attachment_ids

    def test_none_value_not_collected(self, enable_factory_create):
        context = setup_context(
            {},
            rule_schema={"att_field": {"gg_validation": {"rule": "attachment"}}},
            attachment_ids=[],
        )
        process_rule_schema_for_context(context)
        assert context.attachment_ids == set()

    def test_list_field_all_ids_collected(self, enable_factory_create):
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        context = setup_context(
            {"att_list_field": [id1, id2]},
            rule_schema={"att_list_field": {"gg_validation": {"rule": "attachment"}}},
            attachment_ids=[id1, id2],
        )
        process_rule_schema_for_context(context)
        assert context.attachment_ids == {id1, id2}

    def test_multiple_fields_all_collected(self, enable_factory_create):
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        context = setup_context(
            {"att_field": id1, "att_list_field": [id2]},
            rule_schema={
                "att_field": {"gg_validation": {"rule": "attachment"}},
                "att_list_field": {"gg_validation": {"rule": "attachment"}},
            },
            attachment_ids=[id1, id2],
        )
        process_rule_schema_for_context(context)
        assert context.attachment_ids == {id1, id2}

    def test_non_attachment_fields_not_collected(self, enable_factory_create):
        """A UUID in a plain (non-attachment) field is not collected."""
        att_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        context = setup_context(
            {"att_field": att_id, "plain_field": other_id},
            rule_schema={"att_field": {"gg_validation": {"rule": "attachment"}}},
            attachment_ids=[att_id],
        )
        process_rule_schema_for_context(context)
        assert context.attachment_ids == {att_id}
        assert other_id not in context.attachment_ids

    def test_no_rule_schema_empty_collection(self, enable_factory_create):
        att_id = str(uuid.uuid4())
        context = setup_context(
            {"att_field": att_id},
            rule_schema=None,
            attachment_ids=[att_id],
        )
        process_rule_schema_for_context(context)
        assert context.attachment_ids == set()
