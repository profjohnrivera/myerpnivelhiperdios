# backend/tools/audit_legacy_core.py

from __future__ import annotations

import ast
import pathlib
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional


ROOT = pathlib.Path(__file__).resolve().parents[1]
THIS_FILE = pathlib.Path(__file__).resolve()

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "venv",
    ".venv",
    "node_modules",
    "dist",
    "build",
}

PY_FILE_SUFFIXES = {".py"}

# Archivos donde SÍ se tolera pool.acquire() sobre un pool real.
# Esto NO contradice el contrato único de get_connection():
# son capas dueñas de infraestructura o de fallback explícito.
POOL_ACQUIRE_ALLOWLIST = {
    "backend/app/core/storage/postgres_storage.py",
    "backend/app/core/tree.py",
    "backend/app/core/worker.py",
    "backend/app/main.py",
    "backend/fix_db.py",
    "backend/modules/core_system/models/ir_sequence.py",
}

# Archivos donde tiene sentido buscar campos fantasmas de ventas.
GHOST_SALES_PATH_HINTS = (
    "mod_sales",
    "sale_order",
    "sdui",
    "scaffolder",
)

GHOST_SALES_REGEX = re.compile(
    r"\b(sale_order_template_id|tax_label|client_order_ref|payment_term_id|validity_date|note)\b"
)

X2MANY_LEGACY_SYMBOLS = {
    "extract_x2many_data",
    "process_nested_records",
}


@dataclass
class Finding:
    kind: str
    file: str
    line_no: int
    line: str
    detail: str = ""


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT.parent).as_posix()


def iter_python_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in PY_FILE_SUFFIXES:
            continue
        if path.resolve() == THIS_FILE:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def safe_read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def get_source_line(text: str, line_no: int) -> str:
    lines = text.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].rstrip()
    return ""


def parse_ast(path: pathlib.Path, text: str) -> Optional[ast.AST]:
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError:
        return None


class LegacyAuditVisitor(ast.NodeVisitor):
    def __init__(self, path: pathlib.Path, text: str):
        self.path = path
        self.text = text
        self.file_rel = rel(path)
        self.findings: List[Finding] = []

        self.function_stack: List[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.current_hasattr_acquire: List[tuple[int, str]] = []
        self.current_setattrs: List[tuple[int, str]] = []

    def add(self, kind: str, node: ast.AST, detail: str = ""):
        line_no = getattr(node, "lineno", 1)
        self.findings.append(
            Finding(
                kind=kind,
                file=self.file_rel,
                line_no=line_no,
                line=get_source_line(self.text, line_no),
                detail=detail,
            )
        )

    @staticmethod
    def _call_name(node: ast.Call) -> str:
        if isinstance(node.func, ast.Attribute):
            base = LegacyAuditVisitor._expr_name(node.func.value)
            return f"{base}.{node.func.attr}" if base else node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
        return ""

    @staticmethod
    def _expr_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            left = LegacyAuditVisitor._expr_name(node.value)
            return f"{left}.{node.attr}" if left else node.attr
        return ""

    @staticmethod
    def _is_string_literal(node: ast.AST, value: str) -> bool:
        return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == value

    def _path_looks_like_sales_ui(self) -> bool:
        p = self.file_rel.lower()
        return any(hint in p for hint in GHOST_SALES_PATH_HINTS)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._enter_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._enter_function(node)

    def _enter_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        self.function_stack.append(node)

        prev_hasattr = self.current_hasattr_acquire
        prev_setattrs = self.current_setattrs
        self.current_hasattr_acquire = []
        self.current_setattrs = []

        self.generic_visit(node)

        hasattr_targets = {target for _, target in self.current_hasattr_acquire}
        for line_no, target in self.current_setattrs:
            if target in hasattr_targets:
                self.findings.append(
                    Finding(
                        kind="permissive_setattr",
                        file=self.file_rel,
                        line_no=line_no,
                        line=get_source_line(self.text, line_no),
                        detail=f"target={target}",
                    )
                )

        self.current_hasattr_acquire = prev_hasattr
        self.current_setattrs = prev_setattrs
        self.function_stack.pop()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name.endswith("x2many") or alias.name == "x2many":
                self.add("x2many_import", node, detail=alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        if module.endswith("x2many") or module == "x2many":
            self.add("x2many_import", node, detail=module)
        for alias in node.names:
            if alias.name in X2MANY_LEGACY_SYMBOLS:
                self.add("x2many_import", node, detail=alias.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        call_name = self._call_name(node)

        if call_name.endswith("Registry.get_fields_for_model") or call_name == "Registry.get_fields_for_model":
            self.add("registry_alias", node)

        if call_name in X2MANY_LEGACY_SYMBOLS or call_name.endswith(".extract_x2many_data") or call_name.endswith(".process_nested_records"):
            self.add("x2many_import", node, detail=call_name)

        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "hasattr"
            and len(node.args) >= 2
            and self._is_string_literal(node.args[1], "acquire")
        ):
            target = self._expr_name(node.args[0])
            if target in {"conn_or_pool", "pool_or_conn"} or target.endswith(".conn_or_pool") or target.endswith(".pool_or_conn"):
                self.add("manual_pool_contract", node, detail=f"hasattr({target}, 'acquire')")
                self.current_hasattr_acquire.append((getattr(node, "lineno", 1), target))

        if isinstance(node.func, ast.Name) and node.func.id == "setattr" and len(node.args) >= 1:
            target = self._expr_name(node.args[0])
            if target:
                self.current_setattrs.append((getattr(node, "lineno", 1), target))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"conn_or_pool", "pool_or_conn"}:
                self.add("manual_pool_contract", node, detail=f"ambiguous variable '{target.id}'")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load) and node.id in {"conn_or_pool", "pool_or_conn"}:
            self.add("manual_pool_contract", node, detail=f"ambiguous variable usage '{node.id}'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        base = self._expr_name(node.value)

        if node.attr == "acquire" and base in {"conn_or_pool", "pool_or_conn"}:
            self.add("manual_pool_contract", node, detail=f"{base}.acquire")

        if node.attr == "acquire" and base == "pool" and self.file_rel not in POOL_ACQUIRE_ALLOWLIST:
            self.add("manual_pool_contract", node, detail="pool.acquire outside allowlist")

        self.generic_visit(node)

    def visit_arg(self, node: ast.arg):
        if node.arg in {"conn_or_pool", "pool_or_conn"}:
            self.add("manual_pool_contract", node, detail=f"ambiguous parameter '{node.arg}'")
        self.generic_visit(node)


def detect_ghost_sales_fields(path: pathlib.Path, text: str) -> List[Finding]:
    file_rel = rel(path)
    if not any(hint in file_rel.lower() for hint in GHOST_SALES_PATH_HINTS):
        return []

    findings: List[Finding] = []
    for m in GHOST_SALES_REGEX.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        line = get_source_line(text, line_no)

        if line.strip().startswith("#"):
            continue

        findings.append(
            Finding(
                kind="ghost_sales_fields",
                file=file_rel,
                line_no=line_no,
                line=line,
                detail=m.group(0),
            )
        )
    return findings


def detect_x2many_legacy_file(path: pathlib.Path, tree: Optional[ast.AST], text: str) -> List[Finding]:
    file_rel = rel(path)
    if not file_rel.endswith("backend/app/api/v1/x2many.py"):
        return []

    if tree is None:
        return [
            Finding(
                kind="x2many_import",
                file=file_rel,
                line_no=1,
                line=get_source_line(text, 1),
                detail="x2many.py exists but could not parse",
            )
        ]

    fn_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    legacy_hits = sorted(fn_names.intersection(X2MANY_LEGACY_SYMBOLS))
    if legacy_hits:
        return [
            Finding(
                kind="x2many_import",
                file=file_rel,
                line_no=1,
                line=get_source_line(text, 1),
                detail=f"legacy x2many file defines: {', '.join(legacy_hits)}",
            )
        ]

    return []


def scan_file(path: pathlib.Path) -> List[Finding]:
    text = safe_read(path)
    tree = parse_ast(path, text)

    findings: List[Finding] = []

    if tree is not None:
        visitor = LegacyAuditVisitor(path, text)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    findings.extend(detect_ghost_sales_fields(path, text))
    findings.extend(detect_x2many_legacy_file(path, tree, text))

    dedup = {}
    for f in findings:
        key = (f.kind, f.file, f.line_no, f.line, f.detail)
        dedup[key] = f

    return list(dedup.values())


def summarize(findings: List[Finding]) -> str:
    counts = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1

    ordered = [
        "registry_alias",
        "x2many_import",
        "manual_pool_contract",
        "ghost_sales_fields",
        "permissive_setattr",
    ]

    lines = []
    for kind in ordered:
        if kind in counts:
            lines.append(f" - {kind}: {counts[kind]}")
    return "\n".join(lines)


def main() -> int:
    all_findings: List[Finding] = []

    for path in iter_python_files(ROOT):
        all_findings.extend(scan_file(path))

    all_findings.sort(key=lambda f: (f.kind, f.file, f.line_no, f.detail))

    if not all_findings:
        print("✅ Sin consumers legacy críticos detectados.")
        return 0

    print("❌ Se detectaron consumers legacy / contratos ambiguos:\n")

    current_kind = None
    for finding in all_findings:
        if finding.kind != current_kind:
            current_kind = finding.kind
            print(f"\n=== {current_kind} ===")

        suffix = f"  [{finding.detail}]" if finding.detail else ""
        print(f"{finding.file}:{finding.line_no}: {finding.line}{suffix}")

    print("\nResumen:")
    print(summarize(all_findings))

    print(
        "\nCriterios del auditor:\n"
        " - registry_alias      -> llamada real a Registry.get_fields_for_model(...)\n"
        " - x2many_import       -> import/uso real de x2many legacy o x2many.py legacy vivo\n"
        " - manual_pool_contract-> conn_or_pool / pool_or_conn / hasattr(...,'acquire') ambiguo\n"
        " - ghost_sales_fields  -> campos fantasmas en archivos relevantes de ventas/UI\n"
        " - permissive_setattr  -> setattr() junto a hasattr() sobre el mismo target\n"
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())