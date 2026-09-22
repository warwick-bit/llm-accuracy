#!/usr/bin/env python3
"""Advisory hook: nudge the analysis contract on open-ended data prompts."""

from __future__ import annotations

import json
import os
import re
import sys

from accuracy_config import custom_trigger_matches


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
AMBIGUOUS_REVENUE = re.compile(
    r"^\s*(?:"
    r"what(?:'s| is| was)\s+our\s+(?:total\s+)?revenue|"
    r"(?:can\s+you\s+)?(?:tell|show)\s+me\s+(?:what\s+)?our\s+"
    r"(?:total\s+)?revenue(?:\s+is)?|"
    r"how\s+much\s+revenue\s+did\s+we\s+(?:make|generate)"
    r")(?:\s+(?:today|this\s+(?:week|month|quarter|year)|last\s+"
    r"(?:week|month|quarter|year)))?\s*[?.!]*\s*$",
    re.I,
)
AMBIGUOUS_CHANNEL = re.compile(
    r"^\s*which\s+marketing\s+channel\s+"
    r"(?:performs|performed|is|was)\s+best\s*[?.!]*\s*$",
    re.I,
)
AMBIGUOUS_ONBOARDING = re.compile(
    r"^\s*did\s+(?:the\s+)?(?:new\s+)?onboarding\s+(?:flow\s+)?"
    r"improve\s+activation\s*[?.!]*\s*$",
    re.I,
)
AMBIGUOUS_CUSTOMER_RANKING = re.compile(
    r"^\s*who\s+are\s+our\s+(?:best|top)\s+customers\s*[?.!]*\s*$",
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

AMBIGUITY_CONTRACT = (
    "This is a broad business question with more than one reasonable interpretation. "
    "Do not silently choose the definition, population, success measure, time window, "
    "comparison, currency, or source. Ask one short clarification with concrete options, "
    "limited to the choices that would change the answer. {question_guidance} If an "
    "approved metric catalogue is available, use it. If the user asks to proceed without "
    "clarifying, state the assumptions and label the result exploratory. This reminder is "
    "advisory: it does not verify a source or make a value canonical. Mute with "
    "`# analysis-ok` or `CC_SKIP_ANALYSIS=1`."
)


def is_ambiguous_business_question(prompt: str) -> bool:
    return any(
        pattern.match(prompt)
        for pattern in (
            AMBIGUOUS_REVENUE,
            AMBIGUOUS_CHANNEL,
            AMBIGUOUS_ONBOARDING,
            AMBIGUOUS_CUSTOMER_RANKING,
        )
    )


def ambiguity_context(prompt: str) -> str:
    if AMBIGUOUS_REVENUE.match(prompt):
        guidance = (
            "For revenue, offer relevant choices such as MRR, ARR, recognised revenue, "
            "invoiced revenue, or cash received, then clarify the period, currency, and source."
        )
    elif AMBIGUOUS_CHANNEL.match(prompt):
        guidance = (
            "For channel performance, clarify the success measure, period, customer "
            "population, and attribution source."
        )
    elif AMBIGUOUS_ONBOARDING.match(prompt):
        guidance = (
            "For onboarding impact, clarify the activation definition, cohort, measurement "
            "window, and comparison or control group."
        )
    else:
        guidance = (
            "For best customers, clarify whether best means revenue, margin, retention, "
            "product use, or growth potential, then clarify the period and population."
        )
    return AMBIGUITY_CONTRACT.format(question_guidance=guidance)


def should_fire(prompt: str) -> bool:
    if not prompt:
        return False
    lowered = prompt.lower()
    if any(marker in lowered for marker in BYPASS_MARKERS):
        return False
    if custom_trigger_matches("analysis", prompt):
        return True
    p = prompt
    if is_ambiguous_business_question(p):
        return True
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
        context = (
            ambiguity_context(prompt)
            if is_ambiguous_business_question(prompt)
            else CONTRACT
        )
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
