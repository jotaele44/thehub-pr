from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

try:
    from common import context_line, looks_like_lifecycle, unique_preserve
except ImportError:  # pragma: no cover
    from tools.ontology.common import context_line, looks_like_lifecycle, unique_preserve

ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "route", "websocket"}
EVENT_CALLS = {"emit", "publish", "dispatch", "send_event", "record_event", "add_event"}
COMMAND_DECORATORS = {"command", "group"}
PYTHON_MODEL_BASES = {"BaseModel", "SQLModel", "DeclarativeBase", "TypedDict", "Protocol"}
ENUM_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}

class PythonScannerMixin:
    def _scan_python(self, path: Path, text: str) -> None:
        tree = ast.parse(text, filename=str(path))
        lines = text.splitlines()
        artifact = self._artifact_kind(path)
        class_stack: list[str] = []

        def dotted(node: ast.AST | None) -> str:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                left = dotted(node.value)
                return f"{left}.{node.attr}" if left else node.attr
            return ""

        def literal(node: ast.AST) -> Any:
            try:
                return ast.literal_eval(node)
            except Exception:
                return None

        def annotation_text(node: ast.AST | None) -> str | None:
            if node is None:
                return None
            try:
                return ast.unparse(node)
            except Exception:
                return dotted(node) or type(node).__name__

        scanner = self

        class Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                bases = [dotted(base).split(".")[-1] for base in node.bases]
                decorators = [dotted(d).split(".")[-1] for d in node.decorator_list]
                if any(base in ENUM_BASES for base in bases):
                    kind = "python_enum"
                elif any(base.endswith("Exception") or base in {"Exception", "Error"} for base in bases) or node.name.endswith(("Error", "Exception")):
                    kind = "error_class"
                elif "dataclass" in decorators:
                    kind = "python_dataclass"
                elif any(base in PYTHON_MODEL_BASES for base in bases):
                    kind = "python_model"
                else:
                    kind = "python_class"
                scanner.emit(path=path, line=node.lineno, symbol=node.name, term=node.name, term_kind=kind, artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.class", data_type="class", authority_surface=scanner.owner)
                class_stack.append(node.name)
                for child in node.body:
                    if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        required = child.value is None
                        ann = annotation_text(child.annotation)
                        cardinality = "many" if ann and any(t in ann for t in ("list[", "List[", "Sequence[", "set[", "Set[")) else "one"
                        value = literal(child.value) if child.value is not None else None
                        lifecycle = value if looks_like_lifecycle(child.target.id) and isinstance(value, (list, tuple, set)) else []
                        scanner.emit(path=path, line=child.lineno, symbol=f"{node.name}.{child.target.id}", term=child.target.id, term_kind="model_field" if kind in {"python_model", "python_dataclass"} else "class_attribute", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, child.lineno), extractor_rule="python.class_field", data_type=ann, cardinality=cardinality, required=required, lifecycle_values=[str(v) for v in lifecycle] if lifecycle else (), authority_surface=scanner.owner)
                    elif kind == "python_enum" and isinstance(child, (ast.Assign, ast.AnnAssign)):
                        target = child.targets[0] if isinstance(child, ast.Assign) and child.targets else child.target
                        if isinstance(target, ast.Name):
                            value_node = child.value
                            value = literal(value_node) if value_node is not None else None
                            scanner.emit(path=path, line=child.lineno, symbol=f"{node.name}.{target.id}", term=str(value) if isinstance(value, str) else target.id, term_kind="enum_member", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, child.lineno), extractor_rule="python.enum_member", data_type="enum", lifecycle_values=[str(value)] if looks_like_lifecycle(node.name) and value is not None else (), authority_surface=scanner.owner)
                self.generic_visit(node)
                class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._visit_function(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._visit_function(node)

            def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        name = dotted(decorator.func).split(".")[-1]
                        if name in ROUTE_METHODS and decorator.args:
                            route = literal(decorator.args[0])
                            if isinstance(route, str):
                                scanner.emit(path=path, line=node.lineno, symbol=node.name, term=route, term_kind="api_route", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.route_decorator", data_type=name.upper(), authority_surface=scanner.owner)
                        if name in COMMAND_DECORATORS:
                            command = literal(decorator.args[0]) if decorator.args else None
                            command = command if isinstance(command, str) else node.name.replace("_", "-")
                            scanner.emit(path=path, line=node.lineno, symbol=node.name, term=command, term_kind="cli_command", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.command_decorator", authority_surface=scanner.owner)
                self.generic_visit(node)

            def visit_Assign(self, node: ast.Assign) -> None:
                value = literal(node.value)
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id.isupper() or looks_like_lifecycle(target.id):
                        lifecycle = value if looks_like_lifecycle(target.id) and isinstance(value, (list, tuple, set)) else ()
                        scanner.emit(path=path, line=node.lineno, symbol=target.id, term=target.id, term_kind="constant", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.constant", data_type=type(value).__name__ if value is not None else None, lifecycle_values=[str(v) for v in lifecycle], authority_surface=scanner.owner)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                name = dotted(node.func).split(".")[-1]
                if name == "add_parser" and node.args:
                    value = literal(node.args[0])
                    if isinstance(value, str): scanner.emit(path=path, line=node.lineno, symbol="add_parser", term=value, term_kind="cli_command", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.argparse_command", authority_surface=scanner.owner)
                elif name == "add_argument" and node.args:
                    for arg in node.args:
                        value = literal(arg)
                        if isinstance(value, str) and value.startswith("-"): scanner.emit(path=path, line=node.lineno, symbol="add_argument", term=value, term_kind="cli_option", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.argparse_option", authority_surface=scanner.owner)
                elif name in EVENT_CALLS and node.args:
                    value = literal(node.args[0])
                    if isinstance(value, str): scanner.emit(path=path, line=node.lineno, symbol=name, term=value, term_kind="event_name", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.event_call", authority_surface=scanner.owner)
                elif name == "parametrize" and node.args:
                    names = literal(node.args[0])
                    if isinstance(names, str):
                        for parameter in [p.strip() for p in names.split(",") if p.strip()]: scanner.emit(path=path, line=node.lineno, symbol="pytest.parametrize", term=parameter, term_kind="test_parameter", artifact_kind="test", evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.pytest_parameter", authority_surface=scanner.owner)
                self.generic_visit(node)

            def visit_Raise(self, node: ast.Raise) -> None:
                exc = node.exc
                name = dotted(exc.func) if isinstance(exc, ast.Call) else dotted(exc)
                if name: scanner.emit(path=path, line=node.lineno, symbol="raise", term=name.split(".")[-1], term_kind="raised_error", artifact_kind=artifact, evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.raise", authority_surface=scanner.owner)
                self.generic_visit(node)

            def visit_Assert(self, node: ast.Assert) -> None:
                terms: list[str] = []
                for child in ast.walk(node.test):
                    if isinstance(child, ast.Name): terms.append(child.id)
                    elif isinstance(child, ast.Attribute): terms.append(child.attr)
                    elif isinstance(child, ast.Constant) and isinstance(child.value, str) and len(child.value) <= 100: terms.append(child.value)
                for term in unique_preserve(terms): scanner.emit(path=path, line=node.lineno, symbol="assert", term=term, term_kind="test_assertion_term", artifact_kind="test", evidence_tier="T1", context=context_line(lines, node.lineno), extractor_rule="python.assert", authority_surface=scanner.owner)
                self.generic_visit(node)

        Visitor().visit(tree)
