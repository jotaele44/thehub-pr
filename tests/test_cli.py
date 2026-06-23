import json


from hub.cli import main

REGISTRY = "registry/producers.yaml"


def test_list_returns_zero(capsys):
    rc = main(["list", "--registry", REGISTRY])
    assert rc == 0
    out = capsys.readouterr().out
    assert "producers" in out


def test_validate_federation_all_missing(tmp_path, capsys):
    rc = main(["validate-federation", "--registry", REGISTRY, "--root", str(tmp_path)])
    assert rc == 1  # none ready -> nonzero, but not a crash
    out = capsys.readouterr().out
    assert "missing_checkout" in out


def test_validate_federation_json_output(tmp_path, capsys):
    main(["validate-federation", "--registry", REGISTRY, "--root", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "producers" in data
    assert "ready_count" in data


def test_graph_report_empty_dir(tmp_path, capsys):
    rc = main(["graph-report", "--in", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "orphan_entities" in out or "orphan" in out


def test_graph_report_json_flag(tmp_path, capsys):
    rc = main(["graph-report", "--in", str(tmp_path), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "orphan_entities" in data


def test_validate_package_valid(valid_package, capsys):
    rc = main(["validate-package", str(valid_package)])
    assert rc == 0
    assert "VALID" in capsys.readouterr().out


def test_validate_package_invalid(tmp_path, capsys):
    rc = main(["validate-package", str(tmp_path)])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().out
