from pathlib import Path

from federation_audit.resolver import build_resolution_index
from federation_audit.strict_scan import strict_scan_federation, strict_scan_repository


def _write(root: Path, relative_path: str, content: str) -> None:
    file_path = root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _repo() -> dict:
    return {
        "id": "fixture-pr",
        "repository": "fixture/fixture-pr",
        "commit": "a" * 40,
        "workspace_directory": "fixture-pr",
        "entry_points": [],
    }


def _fixture(root: Path, *, method: str = "GET") -> None:
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/items')\n"
        "def items(): return []\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        "export default function App() {\n"
        f"  const load = async () => {{ await fetch('/items', {{ method: '{method}' }}); }};\n"
        "  return <button onClick={load}>Load</button>;\n"
        "}\n",
    )


def test_strict_scan_promotes_exact_gui_to_api_binding(tmp_path: Path) -> None:
    root = tmp_path / "fixture-pr"
    _fixture(root)

    traces, index = strict_scan_repository(root, _repo())

    gui_trace = next(trace for trace in traces if trace.surface.get("kind") == "gui-control")
    assert gui_trace.classification == "EXECUTABLE_BY_CONTRACT"
    assert gui_trace.observations["resolved_target"] == "GET /items"
    assert gui_trace.observations["resolver_receipt_digest"]
    assert any(evidence.kind == "resolver-receipt" for evidence in gui_trace.evidence)
    assert len(index.routes) == 1


def test_strict_scan_keeps_method_mismatch_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "fixture-pr"
    _fixture(root, method="POST")

    traces, index = strict_scan_repository(root, _repo())

    gui_trace = next(trace for trace in traces if trace.surface.get("kind") == "gui-control")
    assert gui_trace.classification == "CONTRACT_MISMATCH"
    assert gui_trace.observations["contract_mismatch"] is True
    assert "resolver_receipt_digest" not in gui_trace.observations
    assert all(evidence.kind != "resolver-receipt" for evidence in gui_trace.evidence)
    assert len(index.routes) == 1


def test_strict_scan_federation_preserves_missing_repository_arithmetic(tmp_path: Path) -> None:
    manifest = {"repositories": [_repo()]}

    report = strict_scan_federation(tmp_path, manifest)

    assert report["coverage"]["repositories_present"] == 0
    assert report["coverage"]["repositories_missing"] == 1
    assert report["workspace_gaps"] == ["fixture-pr"]
    assert report["traces"] == []


def test_resolution_index_scopes_mount_prefixes_to_imported_router_modules(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "server/first.py",
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/first')\n"
        "@router.get('/items')\ndef items(): return []\n",
    )
    _write(
        tmp_path,
        "server/second.py",
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/second')\n"
        "@router.get('/items')\ndef items(): return []\n",
    )
    _write(
        tmp_path,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "from server.first import router as first_router\n"
        "from server.second import router as second_router\n"
        "app = FastAPI()\n"
        "app.include_router(first_router, prefix='/v1')\n"
        "app.include_router(second_router, prefix='/v2')\n",
    )

    index = build_resolution_index(tmp_path)

    assert {(route.method, route.path, route.source) for route in index.routes} == {
        ("GET", "/v1/first/items", "server/first.py"),
        ("GET", "/v2/second/items", "server/second.py"),
    }


def test_resolution_index_deduplicates_mounts_and_excludes_test_routes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "server/app.py",
        "from fastapi import APIRouter, FastAPI\n"
        "app = FastAPI()\nrouter = APIRouter(prefix='/api')\n"
        "@router.get('/items')\ndef items(): return []\n"
        "app.include_router(router)\napp.include_router(router)\n",
    )
    _write(
        tmp_path,
        "tests/test_app.py",
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/fixture-only')\ndef fixture_only(): return []\n",
    )

    index = build_resolution_index(tmp_path)

    assert [(route.method, route.path, route.source) for route in index.routes] == [
        ("GET", "/api/items", "server/app.py")
    ]


def test_strict_scan_resolves_nested_client_state_update_and_internal_navigation(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import Timeline from "./Timeline";\n'
        'export default function App(){ return <><Route path="/items" element={<div />} />'
        '<Timeline /></>; }\n',
    )
    _write(
        root,
        "frontend/Timeline.jsx",
        'import { useState } from "react";\n'
        'export default function Timeline(){\n'
        ' const [filter, setFilter] = useState("ALL");\n'
        ' const items = [{ href: "/items", title: "Items" }];\n'
        ' return <><button aria-label="Set filter" onClick={() => setFilter((value) => '
        '({ ...value, mode: ">" }))}>{filter}</button>\n'
        '<Link to="/items">Open items</Link></>; }\n',
    )

    traces, _ = strict_scan_repository(root, _repo())
    controls = {trace.surface["label"]: trace for trace in traces if trace.surface["kind"] == "gui-control"}

    assert controls["Set filter"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Set filter"].observations["resolved_target"] == "client-state:filter"
    assert controls["Open items"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Open items"].observations["resolved_target"] == "/items"


def test_strict_scan_resolves_custom_select_state_change(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import { useState } from "react";\n'
        "export default function App() {\n"
        '  const [filter, setFilter] = useState("all");\n'
        '  return <Select value={filter} onValueChange={setFilter}>'
        '<SelectItem value="all">All</SelectItem></Select>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:filter"


def test_strict_scan_resolves_select_updates_to_url_search_params(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import { useSearchParams } from "react-router-dom";\n'
        "export default function App() {\n"
        "  const [params, setParams] = useSearchParams();\n"
        "  const filter = params.get('type') || 'all';\n"
        "  const setFilter = (value) => setParams((previous) => {\n"
        "    const next = new URLSearchParams(previous);\n"
        "    if (value === 'all') next.delete('type'); else next.set('type', value);\n"
        "    return next;\n"
        "  }, { replace: true });\n"
        '  return <Select value={filter} onValueChange={setFilter}>'
        '<SelectItem value="all">All</SelectItem></Select>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:url-search-params:type"


def test_strict_scan_follows_local_use_callback_to_client_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import { useCallback, useState } from "react";\n'
        "export default function App() {\n"
        '  const [open, setOpen] = useState(false);\n'
        "  const toggle = useCallback(() => { setOpen((value) => !value); }, [open]);\n"
        '  return <button aria-label="Toggle panel" onClick={() => toggle()}>Toggle</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:open"


def test_strict_scan_resolves_react_namespaced_state_setters(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import * as React from "react";\n'
        "export default function App() {\n"
        "  const [open, setOpen] = React.useState(false);\n"
        "  const toggle = React.useCallback(() => { setOpen((value) => !value); }, [open]);\n"
        '  return <button onClick={() => toggle()}>Toggle</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:open"


def test_strict_scan_resolves_reducer_dispatch_as_client_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import { useReducer } from "react";\n'
        "export default function App() {\n"
        "  const [selection, dispatch] = useReducer(\n"
        '    (state, action) => action.type === "clear" ? null : state,\n'
        "    null,\n"
        "  );\n"
        '  return <><button onClick={() => dispatch({ type: "clear" })}>Clear</button>'
        "{selection}</>;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:selection"


def test_strict_scan_follows_imported_blob_download_helper(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import { downloadReport } from "./download";\n'
        "export default function App() {\n"
        '  return <button onClick={() => downloadReport()}>Download</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/download.js",
        "export function downloadReport() {\n"
        '  const blob = new Blob(["report"]);\n'
        "  const url = URL.createObjectURL(blob);\n"
        '  const link = document.createElement("a");\n'
        "  link.href = url;\n"
        '  link.download = "report.csv";\n'
        "  link.click();\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "browser:download"


def test_strict_scan_resolves_wrapped_calls_to_multiple_backend_routes(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/items')\ndef save_item(): return {'saved': True}\n"
        "@app.get('/status')\ndef get_status(): return {'ready': True}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { saveItem } from "./api";\n'
        "export default function App() {\n"
        '  return <button onClick={saveItem}>Save</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/api.js",
        "async function requestJSON(path, options = {}) {\n"
        "  return fetch(`${API_BASE}${path}`, options);\n"
        "}\n"
        "export async function saveItem() {\n"
        "  await requestJSON('/items', { method: 'POST' });\n"
        "  await requestJSON('/status');\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "multi-route:POST /items|GET /status"


def test_strict_scan_expands_expression_bodied_gui_handler(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/items')\ndef save_item(): return {'saved': True}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { saveItem } from "./api";\n'
        "export default function App() {\n"
        "  const handleSave = () => refresh();\n"
        "  async function refresh() {\n"
        "    try { return await saveItem(); }\n"
        "    catch (error) { throw error; }\n"
        "  }\n"
        '  return <button onClick={handleSave}>Save</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/api.js",
        "async function requestItem(method) {\n"
        "  return fetch('/items', { method });\n"
        "}\n"
        "export async function saveItem() {\n"
        "  return requestItem('POST');\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "POST /items"


def test_strict_scan_follows_component_callback_prop_to_backend_route(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/items/verify')\ndef verify_item(): return {'verified': True}\n",
    )
    _write(
        root,
        "frontend/StatusActions.jsx",
        "export default function StatusActions({ item, onSetStatus }) {\n"
        '  return <button onClick={() => onSetStatus(item, "Verified")}>Verify</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import StatusActions from "./StatusActions";\n'
        "export default function Page() {\n"
        "  async function setStatus(item, status) {\n"
        "    return fetch('/items/verify', { method: 'POST', body: JSON.stringify({ status }) });\n"
        "  }\n"
        "  return <StatusActions item={{ id: 'item-1' }} onSetStatus={setStatus} />;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "POST /items/verify"


def test_strict_scan_follows_react_query_mutation_callback(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/items/{item_id}')\ndef save_item(item_id: str): return {'saved': True}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { saveItem } from "./api";\n'
        "export default function App() {\n"
        "  const mutation = useMutation({ mutationFn: () => saveItem() });\n"
        '  return <button onClick={() => mutation.mutate()}>Save</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/api.js",
        "export const saveItem = async () => {\n"
        "  return fetch('/items/42', { method: 'POST' });\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "POST /items/{item_id}"


def test_strict_scan_follows_mutate_alias_through_custom_react_query_hook(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.patch('/events/{event_id}')\n"
        "def patch_event(event_id: str): return {'saved': True}\n",
    )
    _write(
        root,
        "frontend/EventDetail.jsx",
        'import { useAckEvent } from "./hooks";\n'
        "export default function EventDetail() {\n"
        "  const { mutate: ack } = useAckEvent();\n"
        '  return <button onClick={() => ack({ id: "E-1", status: "resolved" })}>Resolve</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/hooks.js",
        'import { patchEvent } from "./api";\n'
        "export const useAckEvent = () => useMutation({\n"
        "  mutationFn: ({ id, status }) => patchEvent(id, { resolution_status: status }),\n"
        "});\n",
    )
    _write(
        root,
        "frontend/api.js",
        "export const patchEvent = async (id, data) => fetch(`/events/${id}`, {\n"
        '  method: "PATCH", body: JSON.stringify(data),\n'
        "});\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "PATCH /events/{event_id}"


def test_strict_scan_follows_refetch_alias_through_custom_react_query_hook(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/system/status')\n"
        "def system_status(): return {'status': 'ok'}\n",
    )
    _write(
        root,
        "frontend/SystemPage.jsx",
        'import { useSystemStatus } from "./hooks";\n'
        "export default function SystemPage() {\n"
        "  const { refetch: refreshStatus } = useSystemStatus();\n"
        '  return <button onClick={() => refreshStatus()}>Retry status</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/hooks.js",
        'import { getSystemStatus } from "./api";\n'
        "export const useSystemStatus = () => useQuery({\n"
        "  queryKey: ['system/status'], queryFn: getSystemStatus,\n"
        "});\n",
    )
    _write(
        root,
        "frontend/api.js",
        "const getJSON = (path, fallback = null) => fetch(`${API_BASE}${path}`);\n"
        "export const getSystemStatus = async () => getJSON('/system/status', null);\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "GET /system/status"


def test_strict_scan_traces_component_callback_prop_to_caller_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/TypeFilterSelect.jsx",
        "export default function TypeFilterSelect({ value, onChange }) {\n"
        "  return <Select value={value} onValueChange={onChange}>"
        '<SelectItem value="all">All</SelectItem></Select>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useState } from "react";\n'
        'import TypeFilterSelect from "./TypeFilterSelect";\n'
        "export default function Page() {\n"
        '  const [filter, setFilter] = useState("all");\n'
        '  return <TypeFilterSelect value={filter} onChange={setFilter} />;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["source"].endswith("TypeFilterSelect.jsx"))

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:filter"


def test_strict_scan_traces_wrapped_callback_prop_to_caller_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/NativeSelect.jsx",
        "export default function NativeSelect({ value, onChange }) {\n"
        '  return <select value={value} onChange={(event) => onChange(event.target.value)}>'
        '<option value="all">All</option></select>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useState } from "react";\n'
        'import NativeSelect from "./NativeSelect";\n'
        "export default function Page() {\n"
        '  const [selected, setSelected] = useState("all");\n'
        '  return <NativeSelect value={selected} onChange={setSelected} />;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["source"].endswith("NativeSelect.jsx"))

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:selected"


def test_strict_scan_traces_setter_props_and_inline_callback_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/Rail.tsx",
        "export function Rail({ setSelection }: { setSelection: (selection: unknown) => void }) {\n"
        '  return <button onClick={() => setSelection({ kind: "site", id: "s1" })}>Choose site</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Card.tsx",
        "export function Card({ onClick }: { onClick: () => void }) {\n"
        '  return <button onClick={onClick}>Choose record</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Page.tsx",
        'import { useState } from "react";\n'
        'import { Rail } from "./Rail";\n'
        'import { Card } from "./Card";\n'
        "export default function Page() {\n"
        "  const [selection, setSelection] = useState<unknown>(null);\n"
        "  return <><Rail setSelection={setSelection} />\n"
        '    <Card onClick={() => setSelection({ kind: "contract", id: "c1" })} />\n'
        "  </>;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    controls = {
        trace.surface["label"]: trace
        for trace in traces
        if trace.surface["kind"] == "gui-control"
    }

    assert controls["Choose site"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Choose site"].observations["resolved_target"] == "client-state:selection"
    assert controls["Choose record"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Choose record"].observations["resolved_target"] == "client-state:selection"


def test_strict_scan_traces_nested_callback_through_lazy_typed_component(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/Card.tsx",
        "export function Card({ onClick }: { onClick?: () => void }) {\n"
        "  function callbackNoise() { return; }\n"
        '  return <button onClick={() => onClick?.()}>Open record</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Module.tsx",
        'import { Card } from "./Card";\n'
        "export function Module({ setSelection }: { setSelection: (value: unknown) => void }) {\n"
        '  return <Card onClick={() => setSelection({ kind: "record", id: "r1" })} />;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/App.tsx",
        'import { lazy, useState } from "react";\n'
        'const Module = lazy(() => import("./Module").then((m) => ({ default: m.Module })));\n'
        "export default function App() {\n"
        "  const [selection, setSelection] = useState<unknown>(null);\n"
        "  return <Module setSelection={setSelection} />;\n"
        "}\n",
    )

    traces, index = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert index.resolve_symbol("frontend/App.tsx", "Module") is not None
    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:selection"


def test_strict_scan_traces_state_callbacks_from_arrow_components(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        "const Selector = ({ onChange }) => (\n"
        '  <button onClick={() => onChange("selected")}>Select</button>\n'
        ");\n"
        "export default function App() {\n"
        '  const [value, setValue] = useState("");\n'
        "  return <Selector onChange={setValue} />;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:value"


def test_strict_scan_traces_state_callbacks_from_spread_hook_props(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/useFilter.js",
        "export function useFilter() {\n"
        '  const [search, setSearch] = useState("");\n'
        "  const onFilterChange = (key, value) => setSearch(value);\n"
        "  const filterBarProps = {\n"
        "    search,\n"
        "    onSearch: setSearch,\n"
        "    onFilterChange,\n"
        "  };\n"
        "  return { filterBarProps };\n"
        "}\n",
    )
    _write(
        root,
        "frontend/FilterBar.jsx",
        "export function FilterBar({ search, onSearch, onFilterChange }) {\n"
        "  return (\n"
        "    <>\n"
        '      <input value={search} onChange={(event) => onSearch(event.target.value)} />\n'
        '      <select onChange={(event) => onFilterChange("status", event.target.value)}>\n'
        '        <option value="all">All</option>\n'
        "      </select>\n"
        "    </>\n"
        "  );\n"
        "}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { useFilter } from "./useFilter";\n'
        'import { FilterBar } from "./FilterBar";\n'
        "export default function App() {\n"
        "  const { filterBarProps } = useFilter();\n"
        "  return <FilterBar {...filterBarProps} />;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    controls = [trace for trace in traces if trace.surface["kind"] == "gui-control"]

    assert len(controls) == 2
    assert all(
        trace.classification == "EXECUTABLE_BY_CONTRACT" for trace in controls
    )
    assert all(
        trace.observations["resolved_target"] == "client-state:search"
        for trace in controls
    )


def test_strict_scan_traces_state_setter_returned_by_custom_hook(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/useOverlayState.ts",
        'import { useState } from "react";\n'
        "export function useOverlayState() {\n"
        "  const [closed, setClosed] = useState(false);\n"
        "  return { closed, setClosed };\n"
        "}\n",
    )
    _write(
        root,
        "frontend/Overlay.tsx",
        'import { useOverlayState } from "./useOverlayState";\n'
        "function DismissButton({ setClosed }) {\n"
        '  return <button onClick={() => setClosed(true)}>Dismiss</button>;\n'
        "}\n"
        "export function Overlay() {\n"
        "  const overlay = useOverlayState();\n"
        "  const { closed, setClosed } = overlay;\n"
        '  return closed ? null : <DismissButton setClosed={setClosed} />;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:closed"


def test_strict_scan_follows_callback_returned_by_nested_data_hooks(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.patch('/api/entities/{entity_name}/{entity_id}')\n"
        "def update_entity(entity_name: str, entity_id: str): return {'ok': True}\n",
    )
    _write(
        root,
        "frontend/useEntityData.js",
        "export function useEntityData(entityName) {\n"
        "  // This doesn't interfere with the mutation handler.\n"
        "  const updateMut = useMutation({\n"
        "    mutationFn: ({ id, data }) => federation.entities[entityName].update(id, data),\n"
        "  });\n"
        "  return { update: updateMut.mutateAsync };\n"
        "}\n",
    )
    _write(
        root,
        "frontend/useGate.js",
        'import { useEntityData } from "./useEntityData";\n'
        "export function useGate() {\n"
        '  const { update } = useEntityData("LiveFeedItems");\n'
        "  async function verify(item) {\n"
        "    await update(item.id, { sync_status: 'Verified' });\n"
        "  }\n"
        "  return { verify };\n"
        "}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { useGate } from "./useGate";\n'
        "export default function App() {\n"
        "  const { verify } = useGate();\n"
        '  return <button onClick={() => verify({ id: "item-1" })}>Verify</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == (
        "PATCH /api/entities/{entity_name}/{entity_id}"
    )


def test_strict_scan_follows_callback_props_through_nested_components(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/api/action')\n"
        "def action(): return {'ok': True}\n",
    )
    _write(
        root,
        "frontend/ActionButton.jsx",
        "export function ActionButton({ onAction }) {\n"
        '  return <button onClick={() => onAction?.()}>Run</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/ActionPanel.jsx",
        'import { ActionButton } from "./ActionButton";\n'
        "export function ActionPanel({ onAction }) {\n"
        "  return <ActionButton onAction={onAction} />;\n"
        "}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { ActionPanel } from "./ActionPanel";\n'
        "export default function App() {\n"
        "  const perform = async () => {\n"
        "    await fetch('/api/action', { method: 'POST' });\n"
        "  };\n"
        "  return <ActionPanel onAction={perform} />;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "POST /api/action"


def test_strict_scan_resolves_class_component_state_reset(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/ErrorBoundary.jsx",
        "export default class ErrorBoundary extends React.Component {\n"
        "  constructor(props) { super(props); this.state = { error: new Error('render failure') }; }\n"
        "  render() {\n"
        "    const { error } = this.state;\n"
        "    if (!error) return this.props.children;\n"
        "    return <><button onClick={() => this.setState({ error: null })}>Try again</button>\n"
        "    <button onClick={() => window.location.reload()}>Reload</button></>;\n"
        "  }\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    buttons = {
        trace.surface["label"]: trace
        for trace in traces
        if trace.surface["kind"] == "gui-control"
    }

    assert buttons["Try again"].classification == "EXECUTABLE_BY_CONTRACT"
    assert buttons["Try again"].observations["resolved_target"] == "client-state:error"
    assert buttons["Reload"].classification == "EXECUTABLE_BY_CONTRACT"
    assert buttons["Reload"].observations["resolved_target"] == "browser:reload"


def test_strict_scan_resolves_one_control_updating_multiple_local_states(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/Upload.jsx",
        "export default function Upload() {\n"
        "  const [file, setFile] = useState(null);\n"
        "  const [error, setError] = useState('');\n"
        "  const [result, setResult] = useState(null);\n"
        "  return <><input type=\"file\" onChange={(event) => {\n"
        "    setFile(event.target.files[0]); setError(''); setResult(null);\n"
        "  }} /><span>{error}{result}</span><span>{file?.name}</span></>;\n"
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:error,file,result"


def test_strict_scan_resolves_literal_location_navigation_only_to_known_route(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import { useNavigate } from "react-router-dom";\n'
        'export default function App(){ const navigate=useNavigate(); return <>\n'
        '<Route path="/" element={<div />} />\n'
        '<button onClick={() => window.location.href = "/"}>Go home</button>\n'
        '<button onClick={() => navigate("/")}>Go home internally</button>\n'
        '<button onClick={() => window.location.assign("/missing")}>Missing</button>\n'
        '</>; }\n',
    )

    traces, _ = strict_scan_repository(root, _repo())
    controls = {trace.surface["label"]: trace for trace in traces if trace.surface["kind"] == "gui-control"}

    assert controls["Go home"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Go home"].observations["resolved_target"] == "/"
    assert controls["Go home internally"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Go home internally"].observations["resolved_target"] == "/"
    assert controls["Missing"].classification == "TARGET_MISSING"


def test_resolution_index_finds_exported_function_with_nested_default_call(tmp_path: Path):
    _write(
        tmp_path,
        "frontend/helpers.js",
        "export function readRows(limit = Math.max(1, getDefaultLimit())) { return []; }\n",
    )
    _write(
        tmp_path,
        "frontend/App.jsx",
        'import { readRows } from "./helpers";\n'
        "export default function App() { return readRows(); }\n",
    )

    index = build_resolution_index(tmp_path)
    target = index.resolve_symbol("frontend/App.jsx", "readRows")

    assert target is not None
    assert target.source == "frontend/helpers.js"
    assert target.exported is True


def test_resolution_index_resolves_configured_frontend_alias_import(tmp_path: Path):
    _write(
        tmp_path,
        "frontend/jsconfig.json",
        '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["./src/*"]}}}',
    )
    _write(
        tmp_path,
        "frontend/src/api/client.js",
        "export const setWriteToken = (token) => token;\n",
    )
    _write(
        tmp_path,
        "frontend/src/pages/Settings.jsx",
        'import { setWriteToken } from "@/api/client";\n'
        "export default function Settings() { return setWriteToken(null); }\n",
    )

    index = build_resolution_index(tmp_path)
    target = index.resolve_symbol("frontend/src/pages/Settings.jsx", "setWriteToken")

    assert target is not None
    assert target.source == "frontend/src/api/client.js"


def test_strict_scan_resolves_form_submit_to_verified_client_storage_helper(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/client.js",
        "const WRITE_TOKEN_STORAGE_KEY = 'write_token';\n"
        "export const setWriteToken = (token) => {\n"
        "  if (token) window.localStorage.setItem(WRITE_TOKEN_STORAGE_KEY, token);\n"
        "  else window.localStorage.removeItem(WRITE_TOKEN_STORAGE_KEY);\n"
        "  appParams.writeToken = token || null;\n"
        "};\n",
    )
    _write(
        root,
        "frontend/Settings.jsx",
        'import { setWriteToken } from "./client";\n'
        "export default function Settings() {\n"
        "  const save = (event) => { event.preventDefault(); setWriteToken(value); };\n"
        "  const clear = () => { setWriteToken(null); };\n"
        "  return <><form onSubmit={save}>\n"
        '    <button type="submit">Save</button>\n'
        "  </form>\n"
        '  <button onClick={clear}>Clear</button></>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    controls = {
        trace.surface["label"]: trace
        for trace in traces
        if trace.surface["kind"] == "gui-control"
    }

    assert controls["Save"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Clear"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Save"].observations["resolved_target"] == "client-storage:write_token"
    assert controls["Clear"].observations["resolved_target"] == "client-storage:write_token"


def test_strict_scan_resolves_dynamic_navigation_only_through_validated_route_set(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/App.jsx",
        'import Timeline from "./Timeline";\n'
        'export default function App(){ return <><Route path="/items" element={<div />} />'
        '<Timeline /></>; }\n',
    )
    _write(
        root,
        "frontend/Timeline.jsx",
        'import { mergeProgramActivity } from "./programActivityEvent";\n'
        'export default function Timeline(){ const items = mergeProgramActivity(); '
        'return <Link to={item.href}>{item.title}</Link>; }\n',
    )
    _write(
        root,
        "frontend/programActivityEvent.js",
        'const PROGRAM_ACTIVITY_ROUTE_PATHS = new Set(["/items"]);\n'
        'const validRoute = (value) => !value || PROGRAM_ACTIVITY_ROUTE_PATHS.has(value);\n'
        'function declaredEvents(items){ return items.map((item) => '
        '({ canonicalRoute: validRoute(item.href) ? item.href : undefined })); }\n'
        'function validateProgramActivityEvent(event){ return validRoute(event?.canonicalRoute); }\n'
        'export function mergeProgramActivity(items, live, nowMs=Date.now()){ '
        'const declared = declaredEvents(items); '
        'const liveRows = live.filter((event) => validateProgramActivityEvent(event)); '
        'return [...declared, ...liveRows]; }\n',
    )

    traces, _ = strict_scan_repository(root, _repo())
    link = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert link.classification == "EXECUTABLE_BY_CONTRACT"
    assert link.observations["resolved_target"] == "PROGRAM_ACTIVITY_ROUTE_PATHS"


def test_strict_scan_follows_query_result_refetch_to_custom_hook(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/items')\ndef items(): return []\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useItems } from "./hooks";\n'
        "export default function Page() {\n"
        "  const itemsQuery = useItems();\n"
        '  return <button onClick={() => itemsQuery.refetch()}>Retry</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/hooks.js",
        'import { getItems } from "./api";\n'
        "export const useItems = () => useQuery({ queryFn: getItems });\n",
    )
    _write(
        root,
        "frontend/api.js",
        "const qs = (filters) => `?${new URLSearchParams(filters)}`;\n"
        "export const getItems = (filters = {}) => getRequiredJSON(`/items${qs(filters)}`);\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "GET /items"


def test_strict_scan_follows_expression_use_callback_to_query_refetch(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/items')\ndef items(): return []\n",
    )
    _write(
        root,
        "frontend/RetryButton.jsx",
        "export default function RetryButton({ onRetry }) {\n"
        '  return <button onClick={() => onRetry()}>Retry</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useItems } from "./hooks";\n'
        'import RetryButton from "./RetryButton";\n'
        "export default function Page() {\n"
        "  const itemsQuery = useItems();\n"
        "  const retryItems = useCallback(() => itemsQuery.refetch(), [itemsQuery.refetch]);\n"
        "  return <RetryButton onRetry={retryItems} />;\n"
        "}\n",
    )
    _write(
        root,
        "frontend/hooks.js",
        'import { getItems } from "./api";\n'
        "export const useItems = () => useQuery({ queryFn: getItems });\n",
    )
    _write(
        root,
        "frontend/api.js",
        "export const getItems = () => fetch('/items');\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "GET /items"


def test_strict_scan_follows_custom_hook_mutation_function_reference(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.post('/items')\ndef save_item(): return {'saved': True}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useSaveItem } from "./hooks";\n'
        "export default function Page() {\n"
        "  const { mutate: save } = useSaveItem();\n"
        '  return <button onClick={() => save()}>Save</button>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/hooks.js",
        'import { postItem } from "./api";\n'
        "export const useSaveItem = () => useMutation({ mutationFn: postItem });\n",
    )
    _write(
        root,
        "frontend/api.js",
        "export const postItem = () => fetch('/items', { method: 'POST' });\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "POST /items"


def test_strict_scan_traces_inline_component_callback_to_url_search_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/FacetSelect.jsx",
        "export default function FacetSelect({ value, onChange }) {\n"
        '  return <select value={value} onChange={onChange}><option value="all">All</option></select>;\n'
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useSearchParams } from "react-router-dom";\n'
        'import FacetSelect from "./FacetSelect";\n'
        "export default function Page() {\n"
        "  const [params, setParams] = useSearchParams();\n"
        "  const filter = params.get('type') || 'all';\n"
        "  const setFilter = (value) => setParams((previous) => {\n"
        "    const next = new URLSearchParams(previous);\n"
        "    next.set('type', value);\n"
        "    return next;\n"
        "  }, { replace: true });\n"
        '  return <FacetSelect value={filter} onChange={(value) => setFilter(value)} />;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(
        trace
        for trace in traces
        if trace.surface["kind"] == "gui-control"
        and trace.surface["source"].endswith("FacetSelect.jsx")
    )

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:url-search-params:type"


def test_strict_scan_traces_context_setter_to_provider_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/SidebarContext.jsx",
        "import { createContext, useContext, useState } from 'react';\n"
        "const SidebarCtx = createContext(null);\n"
        "export const useSidebar = () => useContext(SidebarCtx);\n"
        "export function SidebarProvider({ children }) {\n"
        "  const [collapsed, setCollapsed] = useState(false);\n"
        "  return <SidebarCtx.Provider value={{ collapsed, setCollapsed }}>"
        "{children}</SidebarCtx.Provider>;\n"
        "}\n",
    )
    _write(
        root,
        "frontend/Sidebar.jsx",
        'import { useSidebar } from "./SidebarContext";\n'
        "export default function Sidebar() {\n"
        "  const { collapsed, setCollapsed } = useSidebar();\n"
        '  return <button onClick={() => setCollapsed((value) => !value)}>Toggle</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:collapsed"


def test_strict_scan_classifies_query_client_refetch_as_client_state(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/ReadFailureBoundary.jsx",
        "import { useQueryClient } from '@tanstack/react-query';\n"
        "export default function ReadFailureBoundary() {\n"
        "  const client = useQueryClient();\n"
        '  return <button onClick={() => client.refetchQueries({ type: "active" })}>Retry</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:react-query-cache-refetch"


def test_strict_scan_follows_context_entity_updates_to_backend_routes(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.patch('/api/entities/{entity_name}/{entity_id}')\n"
        "def update_entity(entity_name: str, entity_id: str): return {'saved': True}\n"
        "@app.post('/api/entities/{entity_name}')\n"
        "def create_entity(entity_name: str): return {'created': True}\n",
    )
    _write(
        root,
        "frontend/Data.jsx",
        "import { createContext, useContext, useCallback } from 'react';\n"
        "const ENTITIES = { reviews: 'ManualReviewItems' };\n"
        "const DataContext = createContext(null);\n"
        "export const useData = () => useContext(DataContext);\n"
        "export function DataProvider({ children }) {\n"
        "  const updateRecord = useCallback(async (collection, id, patch) => {\n"
        "    await federation.entities[ENTITIES[collection]].update(id, patch);\n"
        "  }, []);\n"
        "  const createReview = useCallback(async (payload) => {\n"
        "    await federation.entities[ENTITIES.reviews].create(payload);\n"
        "  }, []);\n"
        "  return <DataContext.Provider value={{ updateRecord, createReview }}>"
        "{children}</DataContext.Provider>;\n"
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useData } from "./Data";\n'
        "export default function Page() {\n"
        "  const d = useData();\n"
        '  return <><button onClick={() => d.updateRecord("reviews", "r1", { notes: "ok" })}>Save</button>\n'
        '  <button onClick={() => d.createReview({ item_id: "r2" })}>Create review</button></>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    controls = {
        trace.surface["label"]: trace
        for trace in traces
        if trace.surface["kind"] == "gui-control"
    }

    assert controls["Save"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Save"].observations["resolved_target"] == "PATCH /api/entities/{entity_name}/{entity_id}"
    assert controls["Create review"].classification == "EXECUTABLE_BY_CONTRACT"
    assert controls["Create review"].observations["resolved_target"] == "POST /api/entities/{entity_name}"


def test_strict_scan_resolves_navigation_through_drawer_context(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/DrawerHub.jsx",
        "import { createContext, useContext, useState } from 'react';\n"
        "const DrawerContext = createContext(null);\n"
        "export const useDrawers = () => useContext(DrawerContext);\n"
        "export function DrawerHubProvider({ children }) {\n"
        "  const [stack, setStack] = useState([]);\n"
        "  const push = (kind, id) => setStack((current) => [...current, { kind, id }]);\n"
        "  const open = { asset: (id) => push('asset', id) };\n"
        "  const top = stack[stack.length - 1];\n"
        "  return <DrawerContext.Provider value={{ open }}>{children}"
        "{top?.kind === 'asset' && <AssetDrawer />}</DrawerContext.Provider>;\n"
        "}\n",
    )
    _write(
        root,
        "frontend/Page.jsx",
        'import { useDrawers } from "./DrawerHub";\n'
        "export default function Page() {\n"
        "  const { open } = useDrawers();\n"
        '  return <button onClick={() => open.asset("asset-1")}>Open asset</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "client-state:drawer:asset"


def test_strict_scan_resolves_copy_action_to_browser_clipboard(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/Capture.jsx",
        "export default function Capture({ hash }) {\n"
        "  const copyHash = async () => { await navigator.clipboard?.writeText(hash); };\n"
        '  return <button aria-label="Copy SHA-256 hash" onClick={copyHash}>Copy</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "browser:clipboard"


def test_strict_scan_resolves_file_picker_ref_click(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/Attach.jsx",
        'import { useRef } from "react";\n'
        "export default function Attach() {\n"
        "  const fileInputRef = useRef(null);\n"
        '  return <><input ref={fileInputRef} type="file" onChange={() => {}} />\n'
        '    <button onClick={() => fileInputRef.current?.click()}>Attach</button></>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(
        trace
        for trace in traces
        if trace.surface["kind"] == "gui-control"
        and trace.surface["label"] == "Attach"
    )

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "browser:file-picker"


def test_strict_scan_resolves_safe_dynamic_external_anchor(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/SourceLink.jsx",
        "export default function SourceLink({ item }) {\n"
        '  return item.source_url ? <a href={item.source_url} target="_blank"'
        ' rel="noreferrer" onClick={(event) => event.stopPropagation()}>Source</a> : null;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "browser:external-navigation"


def test_strict_scan_resolves_download_link_to_client_builder_route(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "server/app.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/api/project-signs/{project_id}/html')\n"
        "def project_sign_html(project_id: str): return '<html />'\n",
    )
    _write(
        root,
        "frontend/api/federationClient.js",
        "const projectSigns = {\n"
        "  htmlUrl: (projectId) => {\n"
        "    const base = trimSlash(appParams.apiBaseUrl || '/api');\n"
        "    return `${base}/project-signs/${encode(projectId)}/html`;\n"
        "  },\n"
        "};\n"
        "export const federation = { projectSigns };\n",
    )
    _write(
        root,
        "frontend/ProjectSigns.jsx",
        'import { federation } from "./api/federationClient";\n'
        "export default function ProjectSigns({ projectId }) {\n"
        '  return <a href={federation.projectSigns.htmlUrl(projectId)}'
        ' download={`${projectId}.html`}>Download</a>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == (
        "browser:download:GET /api/project-signs/{project_id}/html"
    )


def test_strict_scan_follows_typed_imports_to_browser_download(tmp_path: Path):
    root = tmp_path / "fixture-pr"
    _write(
        root,
        "frontend/download.ts",
        "export function download(filename: string, content: string): void {\n"
        "  const url = URL.createObjectURL(new Blob([content]));\n"
        "  const anchor = document.createElement('a');\n"
        "  anchor.href = url;\n"
        "  anchor.download = filename;\n"
        "  anchor.click();\n"
        "}\n",
    )
    _write(
        root,
        "frontend/export.ts",
        'import { download } from "./download";\n'
        "export function exportCsv(): void {\n"
        "  download('report.csv', 'id,name');\n"
        "}\n",
    )
    _write(
        root,
        "frontend/App.jsx",
        'import { exportCsv } from "./export";\n'
        "export default function App() {\n"
        '  return <button onClick={() => exportCsv()}>Export</button>;\n'
        "}\n",
    )

    traces, _ = strict_scan_repository(root, _repo())
    control = next(trace for trace in traces if trace.surface["kind"] == "gui-control")

    assert control.classification == "EXECUTABLE_BY_CONTRACT"
    assert control.observations["resolved_target"] == "browser:download"
