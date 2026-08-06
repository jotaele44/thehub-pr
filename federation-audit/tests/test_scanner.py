from pathlib import Path

from federation_audit.scanner import scan_federation


def test_scanner_correlates_controls_and_routes(tmp_path: Path):
    repo = tmp_path / "sample"
    (repo / "api").mkdir(parents=True)
    (repo / "web").mkdir()
    (repo / "api/app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.post('/api/export')\ndef export(): return {'accepted': True}\n"
    )
    (repo / "web/App.jsx").write_text(
        "export function App() {\n"
        " const good = () => { fetch('/api/export', {method: 'POST'}); };\n"
        " return <div>\n"
        "   <button>Dead</button>\n"
        "   <button onClick={missing}>Missing</button>\n"
        "   <button onClick={good}>Export</button>\n"
        " </div>;\n"
        "}\n"
    )
    manifest = {"repositories": [{"repository": "Jotaele44/sample", "commit": "a" * 40, "workspace_directory": "sample"}]}
    result = scan_federation(tmp_path, manifest)
    by_label = {t["surface"]["label"]: t["classification"] for t in result["traces"]}
    assert by_label["Dead"] == "UI_NO_OP"
    assert by_label["Missing"] == "TARGET_MISSING"
    assert by_label["Export"] == "EXECUTABLE_BY_CONTRACT"
    assert result["coverage"]["by_kind"]["gui-control"] == 3
    assert result["coverage"]["by_kind"]["route"] == 1
