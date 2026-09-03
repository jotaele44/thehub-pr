from federation_audit.fixture import CASES, fixture_passed, run_fixture_audit


def test_all_canonical_fixture_classifications_pass():
    result = run_fixture_audit()
    assert fixture_passed(result) is True
    assert len(result["traces"]) == len(CASES) == 6
    assert {item["classification"] for item in result["traces"]} == {case[2] for case in CASES}
