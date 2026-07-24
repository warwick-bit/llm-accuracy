#!/usr/bin/env python3
"""Advisory hook: nudge the analysis contract on open-ended data prompts."""

from __future__ import annotations

import json
import os
import re
import sys


STRONG = re.compile(
    r"\b(analy[sz]e|segment|break\s?down|cohort|funnel|"
    r"what'?s driving|what is driving|who are our (best|top|power|most|biggest)|"
    r"patterns? in|trends? in)\b",
    re.I,
)
WEAK = re.compile(
    r"\b(investigate|explore|deep[\s-]?dive|profile|"
    r"why (are|is|did|do|aren'?t|isn'?t)|find (out )?(who|what|which|the))\b",
    re.I,
)
DATA_NOUN = re.compile(
    r"\b(users?|customers?|churn|revenue|mrr|arr|retention|conversion|usage|funnel|"
    r"segments?|cohorts?|signups?|leads?|accounts?|orgs?|engagement|activation|pipeline|"
    r"metrics?|power users?|best users?|(the|our) data)\b",
    re.I,
)
LOOKUP = re.compile(
    r"^\s*(what'?s|what is|how many|how much|when|where|who is|list|show|count)\b",
    re.I,
)
EXEC = re.compile(
    r"\b(fix|add|implement|deploy|refactor|merge|push|commit|edit|rename)\b",
    re.I,
)
CONCRETE = re.compile(
    r"[\w/.\-]+\.(py|ts|tsx|md|ya?ml|sh|json|sql)\b|PR\s*#?\d+|~/[\w/.\-]+",
    re.I,
)

BYPASS_MARKERS = ("# analysis-ok", "[analysis-ok]")
BYPASS_ENV = "CC_SKIP_ANALYSIS"

CONTRACT = (
    "This looks like an open-ended data analysis. Hold the analysis contract: "
    "(1) state the obvious cut first; (2) label descriptive vs predictive vs causal; "
    "(3) control denominator, base rate, confounders, selection/survivorship bias, and p-hacking; "
    "(4) no surprise without verification: a counterintuitive finding is a discovery to test, "
    "not a conclusion; (5) for ICP/segment/channel claims, separate survivor pattern reads from "
    "causal claims and check funnel/cohort/source/onboarding/instrumentation bias; "
    "(6) no orphan numbers: quantify only from current-session tool/query evidence; "
    "(7) end decision-useful with evidence level, killed hypotheses, what would change my mind, "
    "and next action. For serious analysis, hold multiple hypotheses before converging and use "
    "parallel evidence checks only when the runtime and user authorization allow delegation. "
    "Skip only for simple lookups. Mute with `# analysis-ok` or `CC_SKIP_ANALYSIS=1`."
)


def should_fire(prompt: str) -> bool:
    if not prompt:
        return False
    lowered = prompt.lower()
    if any(marker in lowered for marker in BYPASS_MARKERS):
        return False
    p = prompt
    if LOOKUP.match(p):
        return False
    if CONCRETE.search(p):
        return False
    strong = bool(STRONG.search(p))
    weak = bool(WEAK.search(p)) and bool(DATA_NOUN.search(p))
    if not (strong or weak):
        return False
    return not (EXEC.search(p) and not (STRONG.search(p[:45]) or WEAK.search(p[:45])))


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
