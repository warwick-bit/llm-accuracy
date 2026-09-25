#!/usr/bin/env python3
"""Fail closed when a distributed plugin contains excluded artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_SUFFIXES = frozenset({".json", ".md", ".py", ".yaml", ".yml"})
COMMON_FORBIDDEN_PATH_PREFIXES = ("verify-number",)
ACCURACY_CORE_FORBIDDEN_PATH_PREFIXES = COMMON_FORBIDDEN_PATH_PREFIXES + (
    "session_ledger",
    "session-ledger",
)
FORBIDDEN_FILE_NAMES = {
    "codex_marketplace_autoupgrade.py",
    "contract-receipts.md",
}
FORBIDDEN_TEXT = (
    "sophiie",
    "soph-investigate",
    "marketplace-autoupgrade",
    "contract-receipt",
)
FORBIDDEN_PYTHON_IMPORT = re.compile(
    r"^\s*(?:from\s+(?:requests|urllib|httpx|socket)\b|"
    r"import\s+(?:requests|urllib|httpx|socket)(?:\s|,|$))",
    re.MULTILINE,
)
SUBPROCESS_IMPORT = re.compile(
    r"^\s*(?:from\s+subprocess\b|import\s+subprocess(?:\s|,|$))", re.MULTILINE
)
# Explicit, user-invoked diagnostics only; automatic hooks get no exception.
ACCURACY_DIAGNOSTICS = frozenset(
    {"scripts/accuracy_doctor.py", "scripts/host_probe.py"}
)


def forbidden_path_prefixes(profile: str) -> tuple[str, ...]:
    """Return the excluded path prefixes for one named distribution profile."""
    if profile == "accuracy-core":
        return ACCURACY_CORE_FORBIDDEN_PATH_PREFIXES
    if profile == "session-ledger":
        return COMMON_FORBIDDEN_PATH_PREFIXES
    if profile == "evidence-memory":
        return COMMON_FORBIDDEN_PATH_PREFIXES
    if profile == "deterministic-data":
        return ACCURACY_CORE_FORBIDDEN_PATH_PREFIXES
    raise ValueError(f"unknown distribution-boundary profile: {profile}")


def artifact_violations(
    path: Path,
    relative: Path,
    *,
    forbidden_prefixes: tuple[str, ...],
    allow_subprocess: bool = False,
) -> list[str]:
    """Return boundary violations for one plugin artifact."""
    display_path = relative.as_posix()
    if path.is_symlink():
        return [f"symlink artifact: {display_path}"]
    if (
        any(part.lower().startswith(forbidden_prefixes) for part in relative.parts)
        or path.name.lower() in FORBIDDEN_FILE_NAMES
    ):
        return [f"excluded artifact: {display_path}"]
    if path.is_dir():
        return []
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return [f"unexpected non-text artifact: {display_path}"]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"unreadable text artifact: {display_path}"]
    violations = [
        f"internal reference: {display_path}"
        for term in FORBIDDEN_TEXT
        if term in text.lower()
    ]
    if path.suffix.lower() == ".py" and (
        FORBIDDEN_PYTHON_IMPORT.search(text)
        or (SUBPROCESS_IMPORT.search(text) and not allow_subprocess)
    ):
        violations.append(f"network-capable import: {display_path}")
    return violations


def boundary_violations(plugin: Path, *, profile: str = "accuracy-core") -> list[str]:
    """Return deterministic, safe-to-report boundary violations for a plugin tree."""
    forbidden_prefixes = forbidden_path_prefixes(profile)
    violations: list[str] = []
    for path in plugin.rglob("*"):
        relative = path.relative_to(plugin)
        if "__pycache__" in relative.parts:
            continue
        violations.extend(
            artifact_violations(
                path,
                relative,
                forbidden_prefixes=forbidden_prefixes,
                allow_subprocess=profile == "accuracy-core"
                and relative.as_posix() in ACCURACY_DIAGNOSTICS,
            )
        )
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin", type=Path)
    parser.add_argument(
        "--profile",
        choices=("accuracy-core", "session-ledger", "evidence-memory", "deterministic-data"),
        default="accuracy-core",
    )
    args = parser.parse_args()
    violations = boundary_violations(args.plugin, profile=args.profile)
    if violations:
        print("Distribution boundary violation:", file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
