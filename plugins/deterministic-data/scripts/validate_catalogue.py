#!/usr/bin/env python3
"""Validate a deterministic-data catalogue without reading any provider data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROOT_KEYS = {"schema_version", "catalogue_id", "definitions"}
DEFINITION_KEYS = {
    "definition_id",
    "label",
    "aliases",
    "status",
    "definition",
    "unit",
    "grain",
    "supported_windows",
    "source_binding",
    "caveats",
}


def _text(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit


def _text_list(value: Any, *, limit: int, maximum: int | None = None) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and (maximum is None or len(value) <= maximum)
        and all(_text(item, limit) for item in value)
    )


def validate_catalogue(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["catalogue_not_object"]
    errors: list[str] = []
    if set(payload) != ROOT_KEYS:
        errors.append("root_fields_invalid")
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version_unsupported")
    if not _text(payload.get("catalogue_id"), 128):
        errors.append("catalogue_id_invalid")
    definitions = payload.get("definitions")
    if not isinstance(definitions, list) or not definitions:
        return sorted(set([*errors, "definitions_invalid"]))

    ids: set[str] = set()
    aliases: set[str] = set()
    for definition in definitions:
        if not isinstance(definition, dict) or set(definition) != DEFINITION_KEYS:
            errors.append("definition_fields_invalid")
            continue
        definition_id = definition.get("definition_id")
        if not _text(definition_id, 128) or not ID_RE.fullmatch(definition_id):
            errors.append("definition_id_invalid")
        elif definition_id in ids:
            errors.append("definition_id_duplicate")
        else:
            ids.add(definition_id)
        for key, limit in (
            ("label", 200),
            ("definition", 1000),
            ("unit", 100),
            ("grain", 100),
        ):
            if not _text(definition.get(key), limit):
                errors.append(f"{key}_invalid")
        if not _text_list(definition.get("aliases"), limit=200):
            errors.append("aliases_invalid")
        else:
            for alias in definition["aliases"]:
                normalized = " ".join(alias.lower().split())
                if normalized in aliases:
                    errors.append("alias_duplicate")
                aliases.add(normalized)
        if not _text_list(definition.get("supported_windows"), limit=100):
            errors.append("supported_windows_invalid")
        caveats = definition.get("caveats")
        if not isinstance(caveats, list) or len(caveats) > 20 or any(
            not _text(item, 500) for item in caveats
        ):
            errors.append("caveats_invalid")
        status = definition.get("status")
        if status not in ("approved", "candidate", "gap"):
            errors.append("status_invalid")
        binding = definition.get("source_binding")
        binding_valid = (
            isinstance(binding, dict)
            and set(binding) == {"adapter_id", "query_id"}
            and _text(binding.get("adapter_id"), 128)
            and _text(binding.get("query_id"), 128)
        )
        if status == "approved" and not binding_valid:
            errors.append("approved_without_source_binding")
        if status in ("candidate", "gap") and binding is not None:
            errors.append("nonapproved_with_source_binding")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalogue", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.catalogue.read_text(encoding="utf-8"))
        errors = validate_catalogue(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        errors = ["catalogue_unreadable"]
    result = {
        "authority": "structural_only",
        "schema_version": "1.0",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "statement": "Catalogue structure checked only; source truth, access, and domain approval were not verified.",
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
