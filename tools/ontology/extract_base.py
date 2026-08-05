from __future__ import annotations

from collections import Counter
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from common import (
        context_line, detect_scale_from_context, detect_unit, exclusion_reason, git_head,
        normalize_label, read_text, sha256_text, stable_observation_id, tracked_files, unique_preserve,
    )
except ImportError:  # pragma: no cover
    from tools.ontology.common import (
        context_line, detect_scale_from_context, detect_unit, exclusion_reason, git_head,
        normalize_label, read_text, sha256_text, stable_observation_id, tracked_files, unique_preserve,
    )

@dataclass(frozen=True)
class Observation:
    observation_id: str
    repository: str
    program_id: str
    commit: str
    path: str
    line: int
    symbol: str
    term: str
    normalized_label: str
    term_kind: str
    artifact_kind: str
    evidence_tier: str
    owner: str
    data_type: str | None
    cardinality: str | None
    required: bool | None
    unit: str | None
    scale: str | None
    lifecycle_values: list[str] = field(default_factory=list)
    authority_surface: str | None = None
    context: str = ""
    context_hash: str = ""
    extractor_rule: str = ""

class RepositoryScannerBase:
    def __init__(self, spec: Mapping[str, str], root: Path) -> None:
        self.spec = spec
        self.root = root
        self.lines_by_path: dict[Path, list[str]] = {}
        self.records: list[Observation] = []
        self.failures: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []
        self.exclusions: Counter[str] = Counter()
        self.total_tracked = 0
        self.eligible_files = 0
        self.scanned_files = 0

    @property
    def repository(self) -> str:
        return str(self.spec["repository"])

    @property
    def program_id(self) -> str:
        return str(self.spec["program_id"])

    @property
    def commit(self) -> str:
        return str(self.spec["commit"])

    @property
    def owner(self) -> str:
        return str(self.spec.get("owner", self.program_id))

    def emit(
        self,
        *,
        path: Path,
        line: int,
        symbol: str,
        term: str,
        term_kind: str,
        artifact_kind: str,
        evidence_tier: str,
        context: str,
        extractor_rule: str,
        data_type: str | None = None,
        cardinality: str | None = None,
        required: bool | None = None,
        unit: str | None = None,
        scale: str | None = None,
        lifecycle_values: Iterable[str] = (),
        authority_surface: str | None = None,
    ) -> None:
        term = str(term).strip()
        if not term or len(term) > 300:
            return
        rel = path.relative_to(self.root).as_posix()
        clean_context = context.strip()[:1000]
        context_hash = sha256_text(clean_context)
        observation_id = stable_observation_id(
            [self.repository, self.commit, rel, str(max(1, line)), symbol, term, context_hash, extractor_rule]
        )
        record = Observation(
            observation_id=observation_id,
            repository=self.repository,
            program_id=self.program_id,
            commit=self.commit,
            path=rel,
            line=max(1, int(line)),
            symbol=symbol or term,
            term=term,
            normalized_label=normalize_label(term),
            term_kind=term_kind,
            artifact_kind=artifact_kind,
            evidence_tier=evidence_tier,
            owner=self.owner,
            data_type=data_type,
            cardinality=cardinality,
            required=required,
            unit=unit or detect_unit(term),
            scale=scale or detect_scale_from_context(clean_context),
            lifecycle_values=unique_preserve(str(v) for v in lifecycle_values if str(v)),
            authority_surface=authority_surface,
            context=clean_context,
            context_hash=context_hash,
            extractor_rule=extractor_rule,
        )
        self.records.append(record)

    def scan(self) -> dict[str, Any]:
        actual_head = git_head(self.root)
        if actual_head is None:
            raise RuntimeError(f"{self.program_id}: workspace is not a Git checkout: {self.root}")
        if actual_head != self.commit:
            raise RuntimeError(
                f"{self.program_id}: pinned commit mismatch; expected {self.commit}, got {actual_head}"
            )
        paths = tracked_files(self.root)
        self.total_tracked = len(paths)
        for path in paths:
            reason = exclusion_reason(path, self.root)
            if reason:
                self.exclusions[reason] += 1
                continue
            self.eligible_files += 1
            try:
                text = read_text(path)
            except Exception as exc:
                self.failures.append({"path": path.relative_to(self.root).as_posix(), "error": f"{type(exc).__name__}: {exc}"})
                continue
            try:
                self._scan_file(path, text)
            except Exception as exc:
                self.warnings.append({"path": path.relative_to(self.root).as_posix(), "warning": f"parser_fallback: {type(exc).__name__}: {exc}"})
                self._scan_lexical_fallback(path, text, exc)
            self.scanned_files += 1
        unique = {record.observation_id: record for record in self.records}
        self.records = sorted(unique.values(), key=lambda r: (r.path, r.line, r.term_kind, r.normalized_label, r.observation_id))
        coverage = 100.0 if self.eligible_files == 0 else round(self.scanned_files / self.eligible_files * 100, 4)
        return {
            "program_id": self.program_id,
            "repository": self.repository,
            "expected_commit": self.commit,
            "actual_commit": actual_head,
            "tracked_files": self.total_tracked,
            "eligible_files": self.eligible_files,
            "scanned_files": self.scanned_files,
            "excluded_files": sum(self.exclusions.values()),
            "exclusions_by_reason": dict(sorted(self.exclusions.items())),
            "failures": self.failures,
            "warnings": self.warnings,
            "coverage_percent": coverage,
            "observations": len(self.records),
        }

    def _scan_lexical_fallback(self, path: Path, text: str, exc: Exception) -> None:
        lines = text.splitlines()
        artifact = self._artifact_kind(path)
        patterns = [
            re.compile(r"^\s*(?:class|interface|enum|type)\s+([A-Za-z_][A-Za-z0-9_]*)"),
            re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]"),
            re.compile(r'\"([A-Za-z_][A-Za-z0-9_.:-]*)\"\s*:'),
        ]
        emitted = 0
        for line_no, line in enumerate(lines, start=1):
            for pattern in patterns:
                for match in pattern.finditer(line):
                    term = match.group(1)
                    self.emit(path=path, line=line_no, symbol=f"fallback:{line_no}:{match.start()}", term=term, term_kind="parser_fallback_identifier", artifact_kind=artifact, evidence_tier="T2", context=context_line(lines, line_no), extractor_rule="lexical.parser_fallback", authority_surface=self.owner)
                    emitted += 1
            if emitted >= 10000:
                break
        if emitted == 0:
            self.emit(path=path, line=1, symbol="parser_fallback", term=path.stem, term_kind="parser_fallback_file", artifact_kind=artifact, evidence_tier="T2", context=f"Parser fallback after {type(exc).__name__}: {exc}", extractor_rule="lexical.parser_fallback_file", authority_surface=self.owner)

    def _scan_file(self, path: Path, text: str) -> None:
        suffix = path.suffix.lower()
        if suffix == ".py": self._scan_python(path, text)
        elif suffix == ".json": self._scan_json(path, text)
        elif suffix == ".jsonl": self._scan_jsonl(path, text)
        elif suffix in {".yaml", ".yml"}: self._scan_yaml(path, text)
        elif suffix == ".toml": self._scan_toml(path, text)
        elif suffix in {".ini", ".cfg"}: self._scan_ini(path, text)
        elif suffix == ".csv": self._scan_csv(path, text)
        elif suffix in {".md", ".rst", ".txt"}: self._scan_docs(path, text)
        elif suffix in {".ts", ".tsx", ".js", ".jsx"}: self._scan_js(path, text)

    def _artifact_kind(self, path: Path) -> str:
        rel = path.relative_to(self.root).as_posix().lower()
        name = path.name.lower()
        if "test" in path.parts or name.startswith("test_") or name.endswith("_test.py"): return "test"
        if "schema" in name or "/schemas/" in f"/{rel}": return "schema"
        if name == "federation.json" or "manifest" in name: return "manifest"
        if any(token in rel for token in ("config/", "registry/", ".github/workflows/")) or "config" in name: return "configuration"
        if path.suffix.lower() in {".md", ".rst", ".txt"}: return "documentation"
        if path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}: return "frontend_code"
        return "source_code"
