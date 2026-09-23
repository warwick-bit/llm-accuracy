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

TECHNICAL_FOOTER = (
    "End substantive technical diagnoses, verification claims and evidence-sufficiency "
    "answers (including rejecting or withholding a claim) with this three-line Checked / Gap / Next footer:\n"
    "Checked: actual checks or supplied evidence, with scope\n"
    "Gap: remaining unknowns (or none)\n"
    "Next: smallest useful check or action (or none)\n"
    "Supplied evidence is not a check you performed. Keep headline, body and footer "
    "consistent; a Gap cannot excuse a stronger claim above. Skip this footer for "
    "routine replies and creative requests."
)

GENERAL_CONTRACT = (
    "CLAIM FIDELITY CHECK: Before concluding, identify what the evidence establishes "
    "and what is missing. For each material claim, including intermediate assertions, "
    "check whether a plausible alternative could produce the same observation "
    "without that claim being true. If evidence cannot distinguish it, qualify or "
    "withhold the claim; conclude on the surviving evidence. State supported narrow "
    "facts plainly, without speculative hedging. Separate observations, hypotheses "
    "and unknowns. Check field, units, denominator, environment and version; "
    "all/none claims need coverage beyond previews, samples and truncated output. "
    "A tool call alone is not verification. Test competing causes before declaring "
    "a root cause. Corrections must revisit dependent conclusions; repeated "
    "reversals require rechecking the framing. Use llm-accuracy:verify-technical "
    "for diagnosis and fix checks. Advisory guidance, not independent verification."
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
        return CONTRACT + " " + TECHNICAL_FOOTER if should_fire(prompt) else ""
    if should_fire(prompt):
        return GENERAL_CONTRACT + " " + CONTRACT + " " + TECHNICAL_FOOTER
    return GENERAL_CONTRACT + " " + TECHNICAL_FOOTER


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
