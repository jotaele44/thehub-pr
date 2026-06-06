import json

from hub.validate import validate_package


def test_valid_package_has_no_errors(valid_package):
    assert validate_package(valid_package) == []


def test_missing_manifest(tmp_path):
    errors = validate_package(tmp_path)
    assert errors and "missing manifest.json" in errors[0]


def test_sha256_tamper_is_caught(valid_package):
    # mutate a data file after the manifest's sha256 was computed
    (valid_package / "sources.jsonl").write_text(
        (valid_package / "sources.jsonl").read_text() + "\n"
    )
    errors = validate_package(valid_package)
    assert any("sha256 mismatch" in e for e in errors)


def test_bad_id_pattern_is_caught(valid_package):
    # corrupt the source_id so it no longer matches ^src_[a-f0-9]{32}$
    import hashlib

    rows = (valid_package / "entities.jsonl").read_text().splitlines()
    obj = json.loads(rows[0])
    obj["entity_id"] = "ent_NOT_HEX"
    rows[0] = json.dumps(obj, sort_keys=True)
    (valid_package / "entities.jsonl").write_text("\n".join(rows) + "\n")
    # re-sync the manifest sha so the failure is the schema, not the hash
    manifest = json.loads((valid_package / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["filename"] == "entities.jsonl":
            f["sha256"] = hashlib.sha256((valid_package / "entities.jsonl").read_bytes()).hexdigest()
    (valid_package / "manifest.json").write_text(json.dumps(manifest))
    errors = validate_package(valid_package)
    assert any("entities.jsonl" in e and "entity_id" in e for e in errors)


def test_record_count_mismatch_is_caught(valid_package):
    manifest = json.loads((valid_package / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["stream"] == "sources":
            f["record_count"] = 99
    (valid_package / "manifest.json").write_text(json.dumps(manifest))
    errors = validate_package(valid_package)
    assert any("record_count mismatch" in e for e in errors)
