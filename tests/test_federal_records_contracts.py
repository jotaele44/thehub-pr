import jsonschema

from hub._schemas import STREAM_ID_FIELD, STREAM_SCHEMA, load_schema

NOW = "2026-07-27T16:00:00Z"
LINEAGE = {
    "producer_script": "tests/test_federal_records_contracts.py",
    "producer_phase": "SYNTHETIC_FIXTURE",
    "source_inputs": ["inline"],
    "extraction_method": "fixture",
}


def _fixtures():
    document_id = "doc_" + "1" * 32
    release_id = "relv_" + "2" * 32
    finding_id = "find_" + "3" * 32
    candidate_id = "cand_" + "4" * 32
    return {
        "federal_documents": {
            "document_id": document_id,
            "originating_agency": "Synthetic Agency",
            "custodial_agency": "NARA",
            "repository": "Synthetic Repository",
            "collection_id": None,
            "record_group": "RG TEST",
            "series": None,
            "archival_identifier": "TEST-001",
            "title": "Synthetic Puerto Rico record",
            "document_date_start": "1965-01-01",
            "document_date_end": None,
            "document_type": "memorandum",
            "jurisdiction": "PR",
            "canonical_identity_basis": ["archival_identifier"],
            "confidence": 1.0,
            "lineage": LINEAGE,
            "synthetic": True,
            "created_at": NOW,
            "extracted_at": NOW,
        },
        "federal_document_releases": {
            "release_id": release_id,
            "document_id": document_id,
            "source_id": "src_" + "5" * 32,
            "released_at": NOW,
            "first_observed_at": NOW,
            "baseline_cutoff": "2026-07-27T23:59:59-04:00",
            "release_state": "NEW_DOCUMENT",
            "access_url": "https://example.test/document.pdf",
            "content_sha256": "6" * 64,
            "byte_size": 100,
            "mime_type": "application/pdf",
            "page_count": 1,
            "text_layer_present": True,
            "ocr_status": "not_required",
            "redaction_state": "partially_redacted",
            "attachment_count": 0,
            "parent_release_id": None,
            "acquisition_receipt_id": "receipt_" + "7" * 32,
            "lineage": LINEAGE,
            "synthetic": True,
            "created_at": NOW,
            "extracted_at": NOW,
        },
        "document_findings": {
            "finding_id": finding_id,
            "document_id": document_id,
            "release_id": release_id,
            "page_start": 1,
            "page_end": 1,
            "finding_type": "PUERTO_RICO_DIRECT",
            "matched_form": "Puerto Rico",
            "canonical_entity": "Puerto Rico",
            "municipalities": [],
            "facilities": [],
            "coordinates": [],
            "subject_categories": ["military operations"],
            "context_summary": "Synthetic page-level finding.",
            "evidence_tier": "T1",
            "automated_confidence": 0.9,
            "reviewer_confidence": 1.0,
            "review_status": "human_verified",
            "cointelpro_disposition": "NOT_COINTELPRO",
            "citation": {
                "page": 1,
                "source_url": "https://example.test/document.pdf",
                "content_sha256": "6" * 64,
            },
            "lineage": LINEAGE,
            "synthetic": True,
            "created_at": NOW,
            "extracted_at": NOW,
        },
        "case_activity_candidates": {
            "candidate_id": candidate_id,
            "case_entity_id": "ent_" + "8" * 32,
            "document_id": document_id,
            "finding_id": finding_id,
            "candidate_basis": ["MUNICIPALITY_MATCH"],
            "temporal_distance_seconds": 0,
            "spatial_distance_km": 1.0,
            "shared_facilities": [],
            "shared_entities": ["Puerto Rico"],
            "candidate_score": 0.6,
            "generated_by": "thehub-pr",
            "requires_human_review": True,
            "lineage": LINEAGE,
            "synthetic": True,
            "created_at": NOW,
            "extracted_at": NOW,
        },
        "case_activity_assessments": {
            "assessment_id": "assess_" + "9" * 32,
            "candidate_id": candidate_id,
            "case_id": "OVNIS-SYNTH-001",
            "classification": "DATA_GAP",
            "explanatory_strength": 0.0,
            "evidence_strength": 0.2,
            "reasoning_summary": "Required source unavailable.",
            "supports_conventional_explanation": False,
            "contradicts_case_claim": False,
            "data_gap_codes": ["SOURCE_UNAVAILABLE"],
            "reviewer": "synthetic-reviewer",
            "reviewed_at": NOW,
            "review_status": "adjudicated",
            "lineage": LINEAGE,
            "synthetic": True,
            "created_at": NOW,
            "extracted_at": NOW,
        },
    }


def test_new_streams_are_registered_and_validate():
    for stream, row in _fixtures().items():
        assert stream in STREAM_SCHEMA
        assert stream in STREAM_ID_FIELD
        jsonschema.Draft7Validator(load_schema(STREAM_SCHEMA[stream])).validate(row)


def test_export_manifest_accepts_new_streams():
    manifest_schema = load_schema("federation_export_manifest.schema.json")
    files = []
    for stream in _fixtures():
        files.append(
            {
                "filename": f"{stream}.jsonl",
                "stream": stream,
                "record_count": 1,
                "sha256": "a" * 64,
                "schema_id": STREAM_SCHEMA[stream],
            }
        )
    manifest = {
        "package_id": "pkg_" + "b" * 32,
        "producer": "synthetic-producer",
        "export_contract_version": "1.1.0",
        "mode": "test",
        "created_at": NOW,
        "federation": {
            "producer_repo": "synthetic-producer",
            "hub_parent": "thehub-pr",
        },
        "files": files,
    }
    jsonschema.Draft7Validator(manifest_schema).validate(manifest)
