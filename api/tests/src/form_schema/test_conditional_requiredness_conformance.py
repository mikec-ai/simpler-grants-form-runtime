import json
from pathlib import Path

import pytest

from src.form_schema.jsonschema_validator import validate_json_schema


FIXTURE_PATH = (
    Path(__file__).parents[2] / "fixtures" / "form_conditional_requiredness_conformance.json"
)
CASES = json.loads(FIXTURE_PATH.read_text())


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_conditional_requiredness_matches_shared_fixture(case):
    required_warnings = [
        {"type": issue.type, "field": issue.field, "message": issue.message}
        for issue in validate_json_schema(case["input"], case["schema"])
        if issue.type == "required"
    ]

    expected = [
        {
            "type": "required",
            "field": field,
            "message": f"'{field.rsplit('.', 1)[-1]}' is a required property",
        }
        for field in case["expected_required_fields"]
    ]
    assert required_warnings == expected
