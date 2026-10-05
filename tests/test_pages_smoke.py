"""Smoke test to verify that all Streamlit page modules compile and top-level symbols resolve cleanly."""

from __future__ import annotations

import ast
import builtins
import importlib
from pathlib import Path
import pytest


def test_all_pages_import_cleanly():
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "app" / "pages"
    page_files = sorted(pages_dir.glob("*.py"))
    page_files.append(root / "app" / "main.py")
    
    for pf in page_files:
        if pf.name == "__init__.py":
            continue
        with open(pf, "r", encoding="utf-8") as f:
            code = f.read()
        compiled = compile(code, str(pf), "exec")
        assert compiled is not None

        # Parse AST and verify all top-level from ... import ... statements resolve
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod_name = node.module
                if mod_name.startswith("app.") or mod_name.startswith("core."):
                    mod = importlib.import_module(mod_name)
                    for alias in node.names:
                        assert hasattr(mod, alias.name), f"Module {mod_name} missing {alias.name} imported in {pf.name}"
