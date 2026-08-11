#!/usr/bin/env python3
"""Advisory hook: trigger Fusion Evidence Protocol for source-conflict prompts."""

from __future__ import annotations

import json
import os
import re
import sys


SOURCE_MARKER = re.compile(
    r"\b("
    r"source\s+[abc]|database|data warehouse|analytics system|billing system|"
    r"crm|transcript|permission row|query returned|rows?"
    r"|lifecycle|historical events?"
    r")\b",
    re.I,
)

GAP_OR_CONFLICT = re.compile(
    r"\b("
    r"conflict|mismatch|disagree|different|stale|last synced|historical|"
    r"zero rows?|no successful|failed|http\s*400|missing|blank|null|"
    r"capped|limit\s+\d+|partial|unknown|cannot confirm|not confirm|"
    r"redacted|permission|support_pii\.read|pii|denominator"
    r")\b",
    re.I,
)

ASKS_FOR_EVIDENCE_ANSWER = re.compile(
    r"\b("
    r"what('| i)?s|what is|how many|which|who|did|does|is|are|why|"
    r"summarize|answer|tell me|work out|reconcile|confirm|verify"
    r")\b",
    re.I,
)

CODE_OR_EXECUTION = re.compile(
    r"\b("
    r"diff|pull request|pr\b|review this code|unified diff|implement|fix|"
    r"refactor|deploy|commit|merge|push|write code|edit "
    r")\b|[\w/.-]+\.(py|ts|tsx|js|json|ya?ml|sql|md)\b",
    re.I,
)

GENERAL_ANALYSIS = re.compile(
    r"\b(analy[sz]e|segment|cohort|funnel|forecast|model|trend|growth|icp)\b",
    re.I,
)

BYPASS_MARKERS = ("# fusion-ok", "[fusion-ok]")
BYPASS_ENV = "CC_SKIP_FUSION_EVIDENCE"

CONTRACT = (
    "FUSION EVIDENCE TRIGGER: This prompt has explicit source conflict/gap/permission/capped-result "
    "signals. Apply the Fusion Evidence Protocol before final answer: (1) inventory each source, "
    "grain, timestamp, and failure state; (2) separate current truth from historical events; "
    "(3) do not convert failed queries, zero-row joins, capped rows, missing denominators, or "
    "redacted/permission-limited data into confirmed facts; (4) preserve disagreements in the "
    "answer; (5) if the runtime supports it and the answer is high-impact, run a second-model "
    "challenge/synthesis pass focused only on unsupported claims and missing caveats. Use this "
    "protocol for evidence reconciliation only; do not generalize this trigger to routine "
    "code review. Mute with `# fusion-ok` or `CC_SKIP_FUSION_EVIDENCE=1`."
)


def should_fire(prompt: str) -> bool:
    if not prompt:
        return False
    lowered = prompt.lower()
    if any(marker in lowered for marker in BYPASS_MARKERS):
        return False
    if CODE_OR_EXECUTION.search(prompt):
        return False
    if GENERAL_ANALYSIS.search(prompt) and not SOURCE_MARKER.search(prompt):
        return False
    return bool(
        ASKS_FOR_EVIDENCE_ANSWER.search(prompt)
        and SOURCE_MARKER.search(prompt)
        and GAP_OR_CONFLICT.search(prompt)
    )


def main() -> int:
    if os.environ.get(BYPASS_ENV):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        prompt = payload.get("prompt", "")
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
