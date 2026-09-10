"""Static guards for the Python 3.7.3 controller deployment baseline."""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
COMPATIBILITY_SOURCES = tuple(sorted((ROOT / "device" / "imx6ull").rglob("*.py"))) + (
    ROOT / "pc" / "communication" / "__init__.py",
    ROOT / "pc" / "communication" / "protocol.py",
)
BUILTIN_GENERICS = frozenset({"dict", "list", "set", "tuple", "frozenset", "deque"})


class _ModernAnnotationFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "enum" and any(alias.name == "StrEnum" for alias in node.names):
            self.errors.append("uses enum.StrEnum")
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self._check_annotation(node.annotation)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._check_annotation(node.annotation)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_annotation(node.returns)
        self.generic_visit(node)

    def _check_annotation(self, node: ast.AST) -> None:
        if node is None:
            return
        for item in ast.walk(node):
            if isinstance(item, ast.BinOp) and isinstance(item.op, ast.BitOr):
                self.errors.append("uses PEP 604 union annotation")
            if isinstance(item, ast.Subscript) and isinstance(item.value, ast.Name) and item.value.id in BUILTIN_GENERICS:
                self.errors.append("uses PEP 585 builtin generic: {0}[...]".format(item.value.id))


class Python37CompatibilityTests(unittest.TestCase):
    def test_controller_sources_avoid_post_37_annotation_features(self) -> None:
        errors = []
        for path in COMPATIBILITY_SOURCES:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            finder = _ModernAnnotationFinder()
            finder.visit(tree)
            errors.extend("{0}: {1}".format(path.relative_to(ROOT), error) for error in finder.errors)
        self.assertEqual(errors, [])

    def test_entrypoint_imports_when_executed_from_repository_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, "device/imx6ull/controller_main.py", "--help"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--mode", completed.stdout)
