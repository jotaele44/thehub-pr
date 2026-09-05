from types import SimpleNamespace
from unittest.mock import Mock

from server.backend.federation_manager_repository_api import _last_receipts


def test_last_receipts_indexes_one_sorted_scan() -> None:
    documents = [
        {"receipt": {"app_id": "hub", "run_id": "old", "finished_at": "2026-01-01T00:00:00Z"}},
        {"receipt": {"app_id": "water", "run_id": "water-1", "finished_at": "2026-01-01T00:00:01Z"}},
        {"receipt": {"app_id": "hub", "run_id": "new", "finished_at": "2026-01-01T00:00:02Z"}},
    ]
    all_documents = Mock(return_value=documents)
    active = SimpleNamespace(runner=SimpleNamespace(receipts=SimpleNamespace(all_documents=all_documents)))

    indexed = _last_receipts(active)

    assert all_documents.call_count == 1
    assert indexed["hub"]["runId"] == "new"
    assert indexed["water"]["runId"] == "water-1"
