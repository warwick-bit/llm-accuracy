#!/usr/bin/env python3
"""Add a bounded claim-fidelity reminder for explicit evidence-boundary prompts."""

from __future__ import annotations

import json
import os
import re
import sys


BYPASS_RE = re.compile(r"#\s*fidelity-ok\b", re.IGNORECASE)
TRIGGER_RE = re.compile(
    r"\b(?:does\s+this\s+prove|can\s+we\s+conclude|claim\s+fidelity|"
    r"evidence\s+supports?|fully\s+sync(?:ed|hronized)|same\s+population|"
    r"complete\s+(?:data|dataset|coverage)|source\s+is\s+current|"
    r"provisional\s+(?:result|calculation)|method\s+(?:matches|aligned)|"
    r"caused\s+by|because\s+of)\b",
    re.IGNORECASE,
)

CONTRACT = (
    "CLAIM FIDELITY CHECK: Keep every load-bearing conclusion inside the observed "
    "source, subject, population, definition, grain, window, freshness and completeness. "
    "A successful read proves only what it returned. Equal counts or totals do not prove "
    "equal membership. A business timestamp does not prove pipeline completeness. A "
    "provisional label does not repair a method/execution mismatch. Preserve conflicts and "
    "unknowns, separate causal claims from measured associations, and name the smallest "
    "additional check needed for any material gap."
)


def should_fire(prompt: str) -> bool:
    return not BYPASS_RE.search(prompt) and bool(TRIGGER_RE.search(prompt))


def main() -> int:
    if os.environ.get("CC_SKIP_CLAIM_FIDELITY") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not should_fire(prompt):
            return 0
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": CONTRACT,
                    }
                }
            )
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
