from pathlib import Path

from federation_audit.scanner import (
    iter_jsx_controls,
    iter_sources,
    jsx_expression_attribute,
    scan_federation,
)


def test_scanner_correlates_controls_and_routes(tmp_path: Path):
    repo = tmp_path / "sample"
    (repo / "api").mkdir(parents=True)
    (repo / "web").mkdir()
    (repo / "api/app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/api/export')\n"
        "def export(): return {'accepted': True}\n"
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
    manifest = {
        "repositories": [
            {"repository": "Jotaele44/sample", "commit": "a" * 40, "workspace_directory": "sample"}
        ]
    }
    result = scan_federation(tmp_path, manifest)
    by_label = {t["surface"]["label"]: t["classification"] for t in result["traces"]}
    assert by_label["Dead"] == "UI_NO_OP"
    assert by_label["Missing"] == "TARGET_MISSING"
    # Static route correlation is evidence of wiring, not proof of target resolution.
    # Promotion to EXECUTABLE_BY_CONTRACT requires an explicit resolver receipt.
    assert by_label["Export"] == "PARTIALLY_WIRED"
    assert result["coverage"]["by_kind"]["gui-control"] == 3
    assert result["coverage"]["by_kind"]["route"] == 1


def test_jsx_control_parser_keeps_nested_handler_expressions_and_arrow_tokens():
    source = (
        '<button onClick={() => setFilter((value) => ({ ...value, label: ">" }))} '
        'className={active ? "on" : "off"}>Apply</button>'
    )

    controls = list(iter_jsx_controls(source))

    assert len(controls) == 1
    assert jsx_expression_attribute(controls[0].attributes, "onClick") == (
        '() => setFilter((value) => ({ ...value, label: ">" }))'
    )
    assert jsx_expression_attribute(controls[0].attributes, "className") == (
        'active ? "on" : "off"'
    )


def test_jsx_control_parser_includes_self_closing_inputs_with_change_handlers():
    controls = list(iter_jsx_controls(
        '<input type="file" onChange={(event) => setFile(event.target.files[0])} />'
    ))

    assert len(controls) == 1
    assert controls[0].tag == "input"
    assert "onChange" in controls[0].attributes
    assert controls[0].body == ""


def test_jsx_control_parser_recognizes_custom_value_change_handlers():
    controls = list(iter_jsx_controls(
        '<Select value={filter} onValueChange={setFilter}><SelectItem value="all" />'
        "</Select>"
    ))

    assert len(controls) == 1
    assert controls[0].tag == "Select"
    assert jsx_expression_attribute(controls[0].attributes, r"onValueChange") == "setFilter"


def test_source_inventory_excludes_test_files_from_production_surfaces(tmp_path: Path):
    production = tmp_path / "frontend" / "src" / "Page.jsx"
    unit_test = tmp_path / "frontend" / "src" / "Page.test.jsx"
    test_directory = tmp_path / "frontend" / "tests" / "example.spec.jsx"
    for path in (production, unit_test, test_directory):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<button onClick={handler}>Action</button>", encoding="utf-8")

    sources = {path.relative_to(tmp_path).as_posix() for path in iter_sources(tmp_path)}

    assert "frontend/src/Page.jsx" in sources
    assert "frontend/src/Page.test.jsx" not in sources
    assert "frontend/tests/example.spec.jsx" not in sources
