import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.form_schema.rule_processing.json_rule_context import JsonRuleConfig, JsonRuleContext
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context

CONFORMANCE_CASES = json.loads(
    (Path(__file__).parents[3] / "fixtures" / "form_calculation_conformance.json").read_text()
)


@pytest.mark.parametrize("case", CONFORMANCE_CASES, ids=lambda case: case["name"])
def test_server_matches_shared_calculation_conformance(case):
    application_form = SimpleNamespace(
        application_response=case["input"],
        application_form_id="calculation-conformance-application-form",
        form_id="calculation-conformance-form",
        form=SimpleNamespace(form_rule_schema=case["rule_schema"]),
    )
    context = JsonRuleContext(
        application_form,
        JsonRuleConfig(
            do_pre_population=True,
            do_post_population=False,
            do_field_validation=False,
        ),
    )
    process_rule_schema_for_context(context)
    assert context.json_data == case["expected"]
