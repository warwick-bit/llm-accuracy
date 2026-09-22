#!/usr/bin/env python3
"""Add general evidence guidance, with an opt-in targeted-only mode.

General mode covers technical requests and terse follow-ups without guessing
their risk from keywords. Subprocess tests live in tests/test_accuracy_wiring.py.
No prompt or evidence is retained or echoed.
"""

from __future__ import annotations

import json
import os
import re
import sys

from accuracy_config import custom_trigger_matches


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

MODE_ENV = "CC_CLAIM_FIDELITY_MODE"
MAX_INPUT_CHARS = 1_000_000

GENERAL_CONTRACT = (
    "CLAIM FIDELITY CHECK: Before material factual claims, check evidence that "
    "actually supports the claim; a tool call alone is not verification. Separate "
    "observations, hypotheses and unknowns. In technical work, verify the measured "
    "field, units, denominator, process/environment and version. Before saying all, "
    "none, total or ruled out, establish coverage beyond previews, samples and "
    "truncated output; otherwise qualify the scope. Test competing causes before "
    "declaring a root cause. When correcting a diagnosis, name the new evidence "
    "and revisit conclusions that depended on it; repeated reversals require "
    "rechecking the framing. Apply these checks before drafting external claims "
    "or declaring a fix verified. Use llm-accuracy:claim-fidelity for consequential "
    "diagnoses. Keep non-factual tasks brief. This is an advisory reminder, not "
    "independent verification."
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
    """Legacy targeted detector; general mode does not depend on vocabulary."""
    if BYPASS_RE.search(prompt):
        return False
    if custom_trigger_matches("claim_fidelity", prompt):
        return True
    if TRIGGER_RE.search(prompt):
        return True
    for report_match in REPORT_CLAIM_RE.finditer(prompt):
        reported_claim = re.split(
            r"(?:[!?]|\.(?=\s|$))", prompt[report_match.end() :], maxsplit=1
        )[0]
        if REPORT_PERCENTAGE_RE.search(reported_claim):
            return True
    return False


def context_for_prompt(prompt: str, mode: str) -> str:
    """Choose bounded guidance without treating prompt text as configuration."""
    if not prompt.strip() or BYPASS_RE.search(prompt):
        return ""
    if mode == "targeted":
        return CONTRACT if should_fire(prompt) else ""
    if should_fire(prompt):
        return GENERAL_CONTRACT + " " + CONTRACT
    return GENERAL_CONTRACT


def main() -> int:
    if os.environ.get("CC_SKIP_CLAIM_FIDELITY") == "1":
        return 0
    try:
        raw = sys.stdin.read(MAX_INPUT_CHARS + 1)
        if len(raw) > MAX_INPUT_CHARS:
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            return 0
        mode = os.environ.get(MODE_ENV, "general").strip().lower()
        context = context_for_prompt(prompt, mode)
        if not context:
            return 0
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": context,
                    }
                }
            )
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
