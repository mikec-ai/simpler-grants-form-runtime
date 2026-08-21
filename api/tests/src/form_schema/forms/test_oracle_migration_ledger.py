import json
from pathlib import Path


def test_oracle_migration_ledger_accounts_for_the_sixteen_form_scope() -> None:
    ledger_path = (
        Path(__file__).parents[4] / "src" / "form_schema" / "forms" / "oracle_migration_ledger.json"
    )
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    forms = ledger["forms"]
    assert len(forms) == 16
    assert len({entry["module"] for entry in forms}) == 16
    assert {entry["status"] for entry in forms} <= {"converted", "partial", "pending"}
    assert sum(entry["status"] == "converted" for entry in forms) == 12
    assert sum(entry["status"] == "partial" for entry in forms) == 1
    assert sum(entry["status"] == "pending" for entry in forms) == 3
    for entry in forms:
        assert (ledger_path.parent / entry["module"]).is_dir()
        if entry["status"] == "converted":
            assert "reuse" in entry
            assert (Path(__file__).parents[4] / entry["parity_test"]).is_file()
