import json

from hub.aggregate import aggregate


def test_aggregate_single_producer(valid_package, tmp_path):
    out = tmp_path / "agg"
    summary = aggregate({"moneysweep-pr": valid_package}, out)
    assert summary["streams"] == {"sources": 1, "entities": 2, "relationships": 1}
    assert summary["errors"]["moneysweep-pr"] == []
    # merged files exist and are valid JSONL
    rows = (out / "entities.jsonl").read_text().splitlines()
    assert len(rows) == 2
    assert all("_producers" in json.loads(r) for r in rows)
    assert (out / "graph_summary.json").exists()


def test_aggregate_dedups_shared_ids_across_producers(package_factory, tmp_path):
    pkg_a = package_factory(tmp_path / "a", producer="moneysweep-pr")
    pkg_b = package_factory(tmp_path / "b", producer="spiderweb-pr")
    out = tmp_path / "agg"
    summary = aggregate({"moneysweep-pr": pkg_a, "spiderweb-pr": pkg_b}, out)
    # identical fixture ids -> deduped, not doubled
    assert summary["streams"]["entities"] == 2
    ent = [json.loads(r) for r in (out / "entities.jsonl").read_text().splitlines()]
    # provenance records both producers
    assert all(set(e["_producers"]) == {"moneysweep-pr", "spiderweb-pr"} for e in ent)


def test_strict_mode_skips_invalid_package(package_factory, tmp_path):
    pkg = package_factory(tmp_path / "good", producer="moneysweep-pr")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text("{ not json")
    out = tmp_path / "agg"
    summary = aggregate({"moneysweep-pr": pkg, "ovnis-pr": bad}, out, strict=True)
    assert summary["errors"]["ovnis-pr"]
    assert "ovnis-pr" not in summary["producers"]
    assert summary["streams"]["sources"] == 1
