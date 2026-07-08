from prii_maintenance import corrections
from prii_maintenance.models import MaintenanceFinding


def test_remove_exact_duplicate_jsonl_rows(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text('{"a":1}\n{"a":1}\n{"a":2}\n', encoding="utf-8")

    removed = corrections.remove_exact_duplicate_jsonl_rows(p)

    assert removed == 1
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines == ['{"a":1}', '{"a":2}']


def test_remove_exact_duplicate_jsonl_rows_noop_when_clean(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    before = p.read_text(encoding="utf-8")

    removed = corrections.remove_exact_duplicate_jsonl_rows(p)

    assert removed == 0
    assert p.read_text(encoding="utf-8") == before


def test_plan_safe_corrections_filters_to_duplicates_with_a_path():
    findings = [
        MaintenanceFinding(finding_id="1", repo="acme-pr", category="duplicate",
                            severity="warning", path="a.jsonl"),
        MaintenanceFinding(finding_id="2", repo="acme-pr", category="schema",
                            severity="error", path="b.json"),
        MaintenanceFinding(finding_id="3", repo="acme-pr", category="duplicate",
                            severity="warning", path=None),
    ]

    planned = corrections.plan_safe_corrections(findings)

    assert [f.finding_id for f in planned] == ["1"]
