#!/usr/bin/env python3
"""Fail closed when the private preview contains excluded artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_SUFFIXES = frozenset({".json", ".md", ".py", ".yaml", ".yml"})
COMMON_FORBIDDEN_PATH_PREFIXES = (
    "verify-number",
)
ACCURACY_CORE_FORBIDDEN_PATH_PREFIXES = COMMON_FORBIDDEN_PATH_PREFIXES + (
    "session_ledger",
    "session-ledger",
)
FORBIDDEN_FILE_NAMES = {
    "contract-receipts.md",
    "codex_marketplace_autoupgrade.py",
}
FORBIDDEN_TEXT = (
    "sophiie",
    "soph-investigate",
    "contract-receipt",
    "marketplace-autoupgrade",
)
FORBIDDEN_PYTHON_IMPORT = re.compile(
    r"^\s*(?:from\s+(?:requests|urllib|httpx|socket|subprocess)\b|"
    r"import\s+(?:requests|urllib|httpx|socket|subprocess)(?:\s|,|$))",
    re.MULTILINE,
)


def boundary_violations(
    plugin: Path, *, profile: str = "accuracy-core"
) -> list[str]:
    """Return deterministic, safe-to-report boundary violations for a plugin tree."""
    if profile not in {"accuracy-core", "session-ledger"}:
        raise ValueError(f"unknown preview-boundary profile: {profile}")
    forbidden_path_prefixes = (
        ACCURACY_CORE_FORBIDDEN_PATH_PREFIXES
        if profile == "accuracy-core"
        else COMMON_FORBIDDEN_PATH_PREFIXES
    )
    violations: list[str] = []
    for path in plugin.rglob("*"):
        relative = path.relative_to(plugin)
        if "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            violations.append(f"symlink artifact: {relative}")
            continue
        if any(
            part.lower().startswith(forbidden_path_prefixes)
            for part in relative.parts
        ) or path.name.lower() in FORBIDDEN_FILE_NAMES:
            violations.append(f"excluded artifact: {relative}")
            continue
        if path.is_dir():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            violations.append(f"unexpected non-text artifact: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            violations.append(f"unreadable text artifact: {relative}")
            continue
        lowered = text.lower()
        if any(term in lowered for term in FORBIDDEN_TEXT):
            violations.append(f"internal reference: {relative}")
        if path.suffix.lower() == ".py" and FORBIDDEN_PYTHON_IMPORT.search(text):
            violations.append(f"network-capable import: {relative}")
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin", type=Path)
    parser.add_argument(
        "--profile",
        choices=("accuracy-core", "session-ledger"),
        default="accuracy-core",
    )
    args = parser.parse_args()
    violations = boundary_violations(args.plugin, profile=args.profile)
    if violations:
        print("Private-preview boundary violation:", file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
