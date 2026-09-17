#!/usr/bin/env python3
"""Add a bounded claim-fidelity reminder for explicit evidence-boundary prompts."""

from __future__ import annotations

import json
import os
import re
import sys


BYPASS_RE = re.compile(r"#\s*fidelity-ok\b", re.IGNORECASE)
TRIGGER_RE = re.compile(
    r"\b(?:does\s+(?:this|that)\s+prove|can\s+we\s+conclude|"
    r"claim\s+fidelity|"
    r"evidence\s+supports?|fully\s+sync(?:ed|hronized)|same\s+population|"
    r"complete\s+(?:data|dataset|coverage)|source\s+is\s+current|"
    r"provisional\s+(?:result|calculation)|method\s+(?:matches|aligned)|"
    r"causal\s+claim|prove\s+caus(?:e|ation))\b",
    re.IGNORECASE,
)
REPORT_CLAIM_RE = re.compile(r"\bcan\s+(?:we|i)\s+report\s+that\b", re.IGNORECASE)
REPORT_PERCENTAGE_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s+percent\b)",
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
    if BYPASS_RE.search(prompt):
        return False
    if TRIGGER_RE.search(prompt):
        return True
    for report_match in REPORT_CLAIM_RE.finditer(prompt):
        reported_claim = re.split(
            r"(?:[!?]|\.(?=\s|$))", prompt[report_match.end() :], maxsplit=1
        )[0]
        if REPORT_PERCENTAGE_RE.search(reported_claim):
            return True
    return False


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
