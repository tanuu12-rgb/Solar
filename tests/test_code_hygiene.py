"""Hygiene test asserting that no module imports random or uses np.random.

Enforces PROJECT_SPEC Section 0 Rule 1 and Section 7.
"""

from pathlib import Path
import re
import pytest
from core.config_loader import get_project_root


def test_no_random_imports() -> None:
    """Assert that no file in the project imports random or uses np.random."""
    root = get_project_root()
    search_dirs = [root / "core", root / "app", root / "tests"]

    forbidden_patterns = [
        re.compile(r"^\s*import\s+random\b", re.MULTILINE),
        re.compile(r"^\s*from\s+random\s+import\b", re.MULTILINE),
        re.compile(r"\bnp\.random\b"),
        re.compile(r"\bnumpy\.random\b"),
    ]

    violations: list[str] = []

    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for py_file in s_dir.rglob("*.py"):
            if py_file.name == "test_code_hygiene.py":
                continue
            content = py_file.read_text(encoding="utf-8")
            for pat in forbidden_patterns:
                match = pat.search(content)
                if match:
                    violations.append(
                        f"Forbidden random usage found in {py_file.relative_to(root)}: '{match.group(0)}'"
                    )

    assert not violations, "\n".join(violations)
