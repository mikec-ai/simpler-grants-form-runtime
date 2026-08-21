import pytest

from src.form_schema.components.numbered_attachment_slots import build_numbered_attachment_slots


def test_numbered_attachment_slots_build_the_exact_runtime_pattern() -> None:
    slots = build_numbered_attachment_slots(15)

    assert tuple(slots.json_schema_properties) == tuple(f"att{i}" for i in range(1, 16))
    assert slots.ui_sections[-1]["label"] == "15) Attachment 15"
    assert slots.rule_schema["att15"] == {"gg_validation": {"rule": "attachment"}}
    assert slots.xml_attachment_fields["att15"] == {
        "xml_element": "ATT15",
        "type": "single_with_wrapper",
    }
    assert {item.classification for item in slots.field_metadata} == {"attachment"}
    assert {item.semantic_question_id for item in slots.field_metadata} == {None}
    assert {item.runtime_path for item in slots.field_metadata} == {
        f"/att{i}" for i in range(1, 16)
    }


@pytest.mark.parametrize("count", [0, 16, True, 1.5])
def test_numbered_attachment_slots_reject_unsupported_counts(count: object) -> None:
    with pytest.raises(ValueError, match="count must be an integer"):
        build_numbered_attachment_slots(count)  # type: ignore[arg-type]


def test_numbered_attachment_slots_allocate_independent_artifacts() -> None:
    first = build_numbered_attachment_slots(1)
    second = build_numbered_attachment_slots(1)
    first.json_schema_properties["att1"]["title"] = "mutated"
    assert second.json_schema_properties["att1"]["title"] == "Attachment 1"
