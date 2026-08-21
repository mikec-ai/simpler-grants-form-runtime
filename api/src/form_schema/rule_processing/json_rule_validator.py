import logging
import re
import typing
from datetime import datetime

from grants_shared.api.response import ValidationErrorDetail
from grants_shared.util.dict_util import get_nested_value

from src.form_schema.rule_processing.json_rule_context import JsonRule, JsonRuleContext
from src.form_schema.rule_processing.json_rule_util import build_path_str
from src.validation.validation_constants import ValidationErrorType

logger = logging.getLogger(__name__)

_DOTTED_FIELD_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _validate_attachment_value(
    context: JsonRuleContext,
    application_attachment_ids: list[str],
    value: typing.Any,
    path: list[str],
    index: int | None = None,
) -> None:
    """Helper function for validating attachment value"""

    # If the attachment ID isn't an expected type
    # then the JSON schema type validation itself
    # should fail anyways, but log a message just
    # in case we need to investigate.
    if not isinstance(value, str):
        logger.info(
            f"Unexpected type found when validating attachment ID: {type(value).__name__}",
            extra={
                "application_form_id": context.application_form.application_form_id,
                "path": build_path_str(path, index=index),
            },
        )
        return

    # Collect the attachment ID regardless of whether it passes validation
    context.attachment_ids.add(value)

    # If the value isn't in the attachment ID list
    # then add a validation error.
    if value not in application_attachment_ids:
        context.validation_issues.append(
            ValidationErrorDetail(
                type=ValidationErrorType.UNKNOWN_APPLICATION_ATTACHMENT,
                message="Field references application_attachment_id not on the application",
                field=build_path_str(path, index=index),
                value=value,
            )
        )


def validate_attachments(context: JsonRuleContext, json_rule: JsonRule) -> None:
    """Validate that the attachment ID field corresponds
    to an actual attachment ID on the application

    Rule is passed in here in case we want to support
    specific configuration, but isn't used at the moment.
    """
    application_attachment_ids = [
        str(application_attachment.application_attachment_id)
        for application_attachment in context.application_form.application.application_attachments
    ]

    # Fetch the value
    value = get_nested_value(context.json_data, json_rule.path)

    # If there is no value currently for an attachment field
    # then we don't do any check, if the field is required, JSON schema
    # validation will handle flagging that where appropriate.
    if value is None:
        return

    # If the value we're validating is a list
    # we need to check each value individually
    if isinstance(value, list):
        for index, v in enumerate(value):
            _validate_attachment_value(
                context=context,
                application_attachment_ids=application_attachment_ids,
                value=v,
                path=json_rule.path,
                index=index,
            )
    else:
        # Otherwise we just need to check the value itself
        _validate_attachment_value(
            context=context,
            application_attachment_ids=application_attachment_ids,
            value=value,
            path=json_rule.path,
            index=None,
        )


def validate_date_not_before(context: JsonRuleContext, json_rule: JsonRule) -> None:
    """Require the target date to be on or after another date field.

    JSON Schema remains responsible for requiredness and date-format errors. This
    rule only adds the cross-field ordering constraint after both operands are
    present and valid ISO calendar dates.
    """

    if set(json_rule.rule) != {"rule", "other_field"}:
        raise ValueError("date_not_before requires exactly 'rule' and 'other_field'")
    other_field = json_rule.rule["other_field"]
    if not isinstance(other_field, str) or not _DOTTED_FIELD_PATH.fullmatch(other_field):
        raise ValueError("date_not_before other_field must be an absolute dotted path")

    target_value = get_nested_value(context.json_data, json_rule.path)
    other_value = get_nested_value(context.json_data, other_field.split("."))
    try:
        target_date = datetime.strptime(target_value, "%Y-%m-%d").date()
        other_date = datetime.strptime(other_value, "%Y-%m-%d").date()
    except TypeError, ValueError:
        return

    if target_date < other_date:
        context.validation_issues.append(
            ValidationErrorDetail(
                type=ValidationErrorType.INVALID_DATE_ORDER,
                message="Date cannot be before the related start date",
                field=build_path_str(json_rule.path),
                value=target_value,
            )
        )


VALIDATION_RULES = {
    "attachment": validate_attachments,
    "date_not_before": validate_date_not_before,
}


def handle_validation(context: JsonRuleContext, json_rule: JsonRule) -> None:
    if not context.config.do_field_validation:
        return

    rule_code: str | None = json_rule.rule.get("rule", None)

    log_extra = context.get_log_context() | json_rule.get_log_context()

    if rule_code is None:
        logger.warning("Rule code is null for configuration", extra=log_extra)
        return
    if rule_code not in VALIDATION_RULES:
        logger.warning("Rule code does not have a defined mapper", extra=log_extra)
        return

    # Run the validation rule, if there are any issues
    # they'll be added to the context
    rule_func = VALIDATION_RULES[rule_code]
    rule_func(context, json_rule)
