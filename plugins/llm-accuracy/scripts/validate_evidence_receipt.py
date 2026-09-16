#!/usr/bin/env python3
"""Validate a generic evidence receipt without retaining or echoing its content."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
ROOT_KEYS = {
    "schema_version",
    "prompt_epoch",
    "claim_id",
    "route_id",
    "definition_id",
    "source_refs",
    "scope",
    "freshness",
    "completeness",
    "conflict",
    "caveats",
    "claim_status",
}
SCOPE_KEYS = {"population", "measure", "time_window", "grain"}
STATEMENT = "Structure checked only; source truth, arithmetic, domain correctness, and factual accuracy were not verified."


def _text(value: Any, *, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit


def _status_block(value: Any, allowed: set[str]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"status", "basis"}
        and value.get("status") in allowed
        and _text(value.get("basis"), limit=500)
    )


def validate_receipt(payload: Any, *, expected_epoch: str | None = None) -> list[str]:
    """Return stable error codes only; never return receipt-provided content."""
    if not isinstance(payload, dict):
        return ["receipt_not_object"]
    errors: list[str] = []
    if set(payload) != ROOT_KEYS:
        errors.append("root_fields_invalid")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_unsupported")
    for key in ("prompt_epoch", "claim_id", "route_id", "definition_id"):
        if not _text(payload.get(key), limit=128):
            errors.append(f"{key}_invalid")
    if expected_epoch is not None and payload.get("prompt_epoch") != expected_epoch:
        errors.append("prompt_epoch_mismatch")

    sources = payload.get("source_refs")
    successful = 0
    source_mismatch = False
    source_unknown = False
    if not isinstance(sources, list) or not sources:
        errors.append("source_refs_invalid")
    else:
        for source in sources:
            if not isinstance(source, dict) or set(source) != {
                "source_id",
                "status",
                "observed_at",
                "scope_match",
            }:
                errors.append("source_ref_invalid")
                continue
            if not _text(source.get("source_id"), limit=128):
                errors.append("source_id_invalid")
            if source.get("status") not in {"success", "failed", "unavailable"}:
                errors.append("source_status_invalid")
            if source.get("status") == "success":
                successful += 1
            observed = source.get("observed_at")
            if observed is not None and not _text(observed, limit=128):
                errors.append("source_observed_at_invalid")
            if source.get("scope_match") not in {"match", "mismatch", "unknown"}:
                errors.append("source_scope_match_invalid")
            source_mismatch = source_mismatch or source.get("scope_match") == "mismatch"
            source_unknown = source_unknown or source.get("scope_match") == "unknown"

    scope = payload.get("scope")
    if not isinstance(scope, dict) or set(scope) != SCOPE_KEYS:
        errors.append("scope_invalid")
    elif any(not _text(scope.get(key), limit=300) for key in SCOPE_KEYS):
        errors.append("scope_value_invalid")
    if not _status_block(payload.get("freshness"), {"current", "stale", "unknown"}):
        errors.append("freshness_invalid")
    if not _status_block(payload.get("completeness"), {"complete", "partial", "unknown"}):
        errors.append("completeness_invalid")
    if not _status_block(payload.get("conflict"), {"none", "present", "unknown"}):
        errors.append("conflict_invalid")
    caveats = payload.get("caveats")
    if (
        not isinstance(caveats, list)
        or len(caveats) > 20
        or any(not _text(item, limit=500) for item in caveats)
    ):
        errors.append("caveats_invalid")

    status = payload.get("claim_status")
    if status not in {"supported", "qualified", "withheld", "unchecked"}:
        errors.append("claim_status_invalid")
    elif status == "supported":
        if successful == 0:
            errors.append("supported_without_successful_source")
        if source_mismatch or source_unknown:
            errors.append("supported_without_scope_match")
        if isinstance(payload.get("freshness"), dict) and payload["freshness"].get("status") != "current":
            errors.append("supported_without_current_source")
        if isinstance(payload.get("completeness"), dict) and payload["completeness"].get("status") != "complete":
            errors.append("supported_without_complete_coverage")
        if isinstance(payload.get("conflict"), dict) and payload["conflict"].get("status") != "none":
            errors.append("supported_with_unresolved_conflict")
    elif status == "qualified":
        if successful == 0:
            errors.append("qualified_without_successful_source")
        if not isinstance(caveats, list) or not caveats:
            errors.append("qualified_without_caveat")
        if source_mismatch:
            errors.append("qualified_with_scope_mismatch")

    return sorted(set(errors))


def result(errors: list[str]) -> dict[str, Any]:
    return {
        "authority": "structural_only",
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "statement": STATEMENT,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", nargs="?", type=Path)
    parser.add_argument("--expected-epoch")
    args = parser.parse_args()
    try:
        raw = args.receipt.read_text(encoding="utf-8") if args.receipt else sys.stdin.read()
        payload = json.loads(raw)
        errors = validate_receipt(payload, expected_epoch=args.expected_epoch)
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors = ["receipt_unreadable"]
    print(json.dumps(result(errors), sort_keys=True, separators=(",", ":")))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
