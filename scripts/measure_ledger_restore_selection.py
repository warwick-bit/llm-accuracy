#!/usr/bin/env python3
"""Synthetic marker-retention comparison; not an LLM accuracy benchmark."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins/session-ledger/hooks/session-ledger.py"


def load_ledger() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ledger", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare_selection() -> dict[str, object]:
    """Score identical synthetic histories against explicit marker oracles."""
    ledger = load_ledger()
    entries = [
        {"role": "user", "text": f"SYNTHETIC_FACT_{index:02d}: " + "x" * 850,
         "fingerprint": f"synthetic-{index}"}
        for index in range(16)
    ]
    # A deliberately simple alternative: reserve a quarter for the oldest fact.
    first = ledger.bounded_entries(entries[:1], limit=ledger.RENDER_ENTRY_BYTES // 4)
    tail = ledger.bounded_entries(entries[1:], limit=ledger.RENDER_ENTRY_BYTES * 3 // 4)
    rendered = {
        "newest": ledger.bounded_context(entries, ""),
        "oldest_quarter_newest_remainder": ledger.context_text(first + tail, "", True),
    }
    cases = {"older_constraint": [0], "latest_correction": [15],
             "recent_constraints": [12, 13, 14, 15]}
    return {
        "scope": "synthetic exact-marker retention, no model calls or accuracy claims",
        "same_history_for_each_policy": True,
        "cases": {
            name: {policy: {"retained": sum(f"SYNTHETIC_FACT_{i:02d}:" in text for i in targets),
                            "required": len(targets)}
                   for policy, text in rendered.items()}
            for name, targets in cases.items()
        },
        "within_serialized_host_limit": {
            policy: ledger.emitted_context_length(text) <= ledger.HOST_CONTEXT_CHARACTER_BUDGET
            for policy, text in rendered.items()
        },
    }


if __name__ == "__main__":
    print(json.dumps(compare_selection(), indent=2, sort_keys=True))
