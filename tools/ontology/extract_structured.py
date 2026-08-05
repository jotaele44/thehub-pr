from __future__ import annotations

import configparser
import csv
import json
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

try:
    from common import context_line, iter_mapping_paths, looks_like_lifecycle, scalar_to_text
except ImportError:  # pragma: no cover
    from tools.ontology.common import context_line, iter_mapping_paths, looks_like_lifecycle, scalar_to_text

DOC_TOKEN_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.:/-]{1,100})`")
DOC_BOLD_DEF_RE = re.compile(r"^\s*[-*]?\s*\*\*([^*]{2,100})\*\*\s*(?:[:—–-]|\|)")
DOC_TABLE_RE = re.compile(r"^\s*\|\s*`?([A-Za-z][A-Za-z0-9_ .:/-]{1,100})`?\s*\|")
JS_DECL_RE = re.compile(r"\b(class|interface|type|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)")
JS_ROUTE_RE = re.compile(r"(?:path\s*[:=]|<Route[^>]*\bpath=)\s*[{\'\"]+([^\'\"}]+)")
JS_EVENT_RE = re.compile(r"\b(?:emit|dispatch|publish)\s*\(\s*[\'\"]([^\'\"]+)[\'\"]")

class StructuredScannerMixin:
    def _scan_json(self, path: Path, text: str) -> None:
        data = json.loads(text)
        if isinstance(data, Mapping) and ("$schema" in data or "properties" in data or "$defs" in data or "definitions" in data):
            self._scan_schema_mapping(path, text, data)
        self._scan_structured_mapping(path, text, data, "json")

    def _scan_jsonl(self, path: Path, text: str) -> None:
        merged_keys: dict[str, Any] = {}
        parsed = 0
        for line in text.splitlines():
            if not line.strip(): continue
            item = json.loads(line); parsed += 1
            if isinstance(item, Mapping):
                for key, value in item.items(): merged_keys.setdefault(str(key), value)
            if parsed >= 1000: break
        for key, value in sorted(merged_keys.items()):
            self.emit(path=path, line=1, symbol=key, term=key, term_kind="record_field", artifact_kind="data_projection", evidence_tier="T2", context=f"JSONL observed field {key!r} across first {parsed} records", extractor_rule="jsonl.field", data_type=type(value).__name__, cardinality="many" if isinstance(value, list) else "one", authority_surface=self.owner)

    def _scan_yaml(self, path: Path, text: str) -> None:
        for index, data in enumerate(yaml.safe_load_all(text)):
            if data is not None: self._scan_structured_mapping(path, text, data, f"yaml_document_{index}")

    def _scan_toml(self, path: Path, text: str) -> None:
        try:
            import tomllib
        except ImportError:
            try: import tomli as tomllib
            except ImportError:
                self._scan_toml_lexical(path, text); return
        self._scan_structured_mapping(path, text, tomllib.loads(text), "toml")

    def _scan_toml_lexical(self, path: Path, text: str) -> None:
        section = ""
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped.strip("[]")
                self.emit(path=path, line=line_no, symbol=section, term=section, term_kind="config_section", artifact_kind=self._artifact_kind(path), evidence_tier="T2", context=stripped, extractor_rule="toml.lexical_section", authority_surface=self.owner)
            elif "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip().strip('"\'')
                if key: self.emit(path=path, line=line_no, symbol=f"{section}.{key}" if section else key, term=key, term_kind="config_key", artifact_kind=self._artifact_kind(path), evidence_tier="T2", context=stripped, extractor_rule="toml.lexical_key", authority_surface=self.owner)

    def _scan_ini(self, path: Path, text: str) -> None:
        parser = configparser.ConfigParser(interpolation=None); parser.read_string(text)
        for section in parser.sections():
            self.emit(path=path, line=1, symbol=section, term=section, term_kind="config_section", artifact_kind=self._artifact_kind(path), evidence_tier="T2", context=f"[{section}]", extractor_rule="ini.section", authority_surface=self.owner)
            for key, value in parser.items(section):
                self.emit(path=path, line=1, symbol=f"{section}.{key}", term=key, term_kind="config_key", artifact_kind=self._artifact_kind(path), evidence_tier="T2", context=f"[{section}] {key}={value}"[:1000], extractor_rule="ini.key", data_type="string", authority_surface=self.owner)

    def _scan_csv(self, path: Path, text: str) -> None:
        reader = csv.reader(text.splitlines())
        try: headers = next(reader)
        except StopIteration: return
        for index, header in enumerate(headers):
            value = header.strip()
            if value: self.emit(path=path, line=1, symbol=f"column[{index}]", term=value, term_kind="tabular_field", artifact_kind="data_projection", evidence_tier="T2", context=",".join(headers)[:1000], extractor_rule="csv.header", cardinality="one", authority_surface=self.owner)

    def _scan_schema_mapping(self, path: Path, text: str, data: Mapping[str, Any]) -> None:
        lines = text.splitlines(); title = data.get("title")
        if isinstance(title, str): self.emit(path=path, line=1, symbol="$title", term=title, term_kind="schema_title", artifact_kind="schema", evidence_tier="T1", context=str(data.get("description", title)), extractor_rule="jsonschema.title", data_type="object", authority_surface=self.owner)
        required = set(str(v) for v in data.get("required", []) if isinstance(v, str))
        properties = data.get("properties", {})
        if isinstance(properties, Mapping):
            for name, spec in properties.items():
                if not isinstance(spec, Mapping): spec = {}
                dtype = spec.get("type")
                if isinstance(dtype, list): dtype_text = "|".join(str(v) for v in dtype)
                elif dtype is None and "$ref" in spec: dtype_text = str(spec["$ref"])
                else: dtype_text = str(dtype) if dtype is not None else None
                enum = spec.get("enum", []); lifecycle = [str(v) for v in enum] if looks_like_lifecycle(str(name)) and isinstance(enum, list) else []
                minimum, maximum = spec.get("minimum"), spec.get("maximum")
                scale = f"{minimum}..{maximum}" if minimum is not None and maximum is not None else None
                description = str(spec.get("description", "")); line_no = next((i for i, line in enumerate(lines, 1) if f'"{name}"' in line), 1)
                self.emit(path=path, line=line_no, symbol=f"properties.{name}", term=str(name), term_kind="schema_property", artifact_kind="schema", evidence_tier="T1", context=(description or context_line(lines, line_no)), extractor_rule="jsonschema.property", data_type=dtype_text, cardinality="many" if dtype == "array" else "one", required=str(name) in required, scale=scale, lifecycle_values=lifecycle, authority_surface=self.owner)
        for defs_key in ("$defs", "definitions"):
            definitions = data.get(defs_key, {})
            if isinstance(definitions, Mapping):
                for name, spec in definitions.items(): self.emit(path=path, line=1, symbol=f"{defs_key}.{name}", term=str(name), term_kind="schema_definition", artifact_kind="schema", evidence_tier="T1", context=str(spec.get("description", "")) if isinstance(spec, Mapping) else str(name), extractor_rule="jsonschema.definition", data_type="schema", authority_surface=self.owner)

    def _scan_structured_mapping(self, path: Path, text: str, data: Any, parser_name: str) -> None:
        artifact = self._artifact_kind(path); tier = "T1" if artifact in {"schema", "manifest", "test"} else "T2"; lines = text.splitlines()
        for key_path, value in iter_mapping_paths(data):
            key = key_path[-1]
            if key.startswith("["): continue
            symbol = ".".join(key_path); line_no = next((i for i, line in enumerate(lines, 1) if re.search(rf"(?:^|[\s\"']){re.escape(key)}(?:[\"']?\s*[:=])", line)), 1)
            scalar = scalar_to_text(value); lifecycle: list[str] = []
            if looks_like_lifecycle(key):
                if isinstance(value, list): lifecycle = [str(v) for v in value if not isinstance(v, (dict, list))]
                elif isinstance(value, str): lifecycle = [value]
            self.emit(path=path, line=line_no, symbol=symbol, term=key, term_kind="manifest_field" if artifact == "manifest" else "config_key", artifact_kind=artifact, evidence_tier=tier, context=(f"{symbol} = {scalar}" if scalar is not None else context_line(lines, line_no)), extractor_rule=f"{parser_name}.mapping_key", data_type=type(value).__name__, cardinality="many" if isinstance(value, list) else "one", lifecycle_values=lifecycle, authority_surface=self.owner)

    def _scan_docs(self, path: Path, text: str) -> None:
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip(); heading = stripped.lstrip("#").strip() if stripped.startswith("#") else None
            if heading and len(heading) <= 200: self.emit(path=path, line=line_no, symbol=f"heading:{line_no}", term=heading, term_kind="document_heading", artifact_kind="documentation", evidence_tier="T4", context=context_line(lines, line_no), extractor_rule="docs.heading", authority_surface=self.owner)
            bold = DOC_BOLD_DEF_RE.match(line)
            if bold: self.emit(path=path, line=line_no, symbol=f"definition:{line_no}", term=bold.group(1).strip(), term_kind="documented_term", artifact_kind="documentation", evidence_tier="T4", context=context_line(lines, line_no), extractor_rule="docs.bold_definition", authority_surface=self.owner)
            table = DOC_TABLE_RE.match(line)
            if table and not set(table.group(1).strip()) <= {"-", ":"}: self.emit(path=path, line=line_no, symbol=f"table:{line_no}", term=table.group(1).strip(), term_kind="documented_table_term", artifact_kind="documentation", evidence_tier="T4", context=context_line(lines, line_no), extractor_rule="docs.table_first_column", authority_surface=self.owner)
            for match in DOC_TOKEN_RE.finditer(line):
                term = match.group(1)
                if len(term) > 1: self.emit(path=path, line=line_no, symbol=f"inline:{line_no}:{match.start()}", term=term, term_kind="documented_identifier", artifact_kind="documentation", evidence_tier="T4", context=context_line(lines, line_no), extractor_rule="docs.inline_code", authority_surface=self.owner)

    def _scan_js(self, path: Path, text: str) -> None:
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for match in JS_DECL_RE.finditer(line):
                kind, name = match.groups(); self.emit(path=path, line=line_no, symbol=name, term=name, term_kind=f"javascript_{kind}", artifact_kind="frontend_code", evidence_tier="T1", context=context_line(lines, line_no), extractor_rule="javascript.declaration", data_type=kind, authority_surface=self.owner)
            for match in JS_ROUTE_RE.finditer(line):
                route = match.group(1).strip(); self.emit(path=path, line=line_no, symbol=f"route:{line_no}", term=route, term_kind="frontend_route", artifact_kind="frontend_code", evidence_tier="T1", context=context_line(lines, line_no), extractor_rule="javascript.route", authority_surface=self.owner)
            for match in JS_EVENT_RE.finditer(line):
                event = match.group(1); self.emit(path=path, line=line_no, symbol=f"event:{line_no}", term=event, term_kind="event_name", artifact_kind="frontend_code", evidence_tier="T1", context=context_line(lines, line_no), extractor_rule="javascript.event", authority_surface=self.owner)
