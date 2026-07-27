import jsonschema

from hub._schemas import STREAM_ID_FIELD, STREAM_SCHEMA, load_schema

EXPECTED = {
    "federal_documents": ("federation_federal_document.schema.json", "document_id"),
    "federal_document_releases": (
        "federation_federal_document_release.schema.json",
        "release_id",
    ),
    "document_findings": ("federation_document_finding.schema.json", "finding_id"),
    "case_activity_candidates": (
        "federation_case_activity_candidate.schema.json",
        "candidate_id",
    ),
    "case_activity_assessments": (
        "federation_case_activity_assessment.schema.json",
        "assessment_id",
    ),
}


def test_new_streams_are_registered():
    for stream, (schema_name, id_field) in EXPECTED.items():
        assert STREAM_SCHEMA[stream] == schema_name
        assert STREAM_ID_FIELD[stream] == id_field


def test_new_schemas_are_valid_draft7():
    for schema_name, _id_field in EXPECTED.values():
        jsonschema.Draft7Validator.check_schema(load_schema(schema_name))


def test_export_manifest_accepts_each_new_stream():
    manifest_schema = load_schema("federation_export_manifest.schema.json")
    validator = jsonschema.Draft7Validator(manifest_schema)
    for stream, (schema_name, _id_field) in EXPECTED.items():
        manifest = {
            "package_id": "pkg_" + "b" * 32,
            "producer": "synthetic-producer",
            "export_contract_version": "1.1.0",
            "mode": "test",
            "created_at": "2026-07-27T16:00:00Z",
            "federation": {
                "producer_repo": "synthetic-producer",
                "hub_parent": "thehub-pr",
            },
            "files": [
                {
                    "filename": f"{stream}.jsonl",
                    "stream": stream,
                    "record_count": 1,
                    "sha256": "a" * 64,
                    "schema_id": schema_name,
                }
            ],
        }
        validator.validate(manifest)
