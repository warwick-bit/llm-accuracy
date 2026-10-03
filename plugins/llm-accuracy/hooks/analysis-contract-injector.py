#!/usr/bin/env python3
"""Advisory hook: nudge the analysis contract on open-ended data prompts."""

from __future__ import annotations

import json
import os
import re
import sys

from hook_input import read_hook_input

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
# "How many new customers did we get in July?" A period or a named file may
# follow; only the opening is fixed.
AMBIGUOUS_NEW_COUNT = re.compile(
    r"^\s*how\s+many\s+new\s+(?:paying\s+|paid\s+)?"
    r"(?:customers|users|accounts|clients|subscribers|sign[\s-]?ups)\s+"
    r"(?:did\s+we\s+(?:get|have|add|gain|acquire|win|sign(?:\s+up)?)|"
    r"have\s+we\s+(?:got|gotten|had|added|gained|acquired|won|signed(?:\s+up)?)|"
    r"were\s+there|do\s+we\s+have)\b",
    re.I,
)
# A count whose definition the prompt already supplies is not ambiguous.
DEFINED_COUNT = re.compile(
    r"\b(?:defined\s+as|definition|distinct|de-?dup\w*|exclud\w*|except|"
    # "unique users", not "unique promo codes"
    r"unique\s+(?:by|per|on|(?:customer|user|account|client|email|id|people|person|"
    r"subscriber|sign[\s-]?up|payer|buyer|visitor)\w*)|"
    r"not\s+counting|only\s+count\w*|counting\s+only|count(?:ing)?\s+(?:each|every|one)|"
    # a first-payment rule, not "the first-order discount code"
    r"first[\s-]+(?:paid|paying|payment|purchase|invoice|order|subscription)"
    r"(?![\s-]+(?:discount|promo|offer|code|coupon|sale|deal|campaign|bonus)s?\b)|"
    r"time[\s-]?zone|utc|gmt|local\s+time(?!-)|"
    # a named zone ("Sydney time", "Pacific Standard Time"), not "peak time" or
    # "the NZ time-limited sale"
    r"(?:pacific|mountain|central|eastern|western|atlantic|alaska|hawaii|australian|"
    r"european|sydney|melbourne|brisbane|queensland|adelaide|perth|darwin|hobart|"
    r"auckland|wellington|nz|new\s+zealand|london|dublin|paris|berlin|new\s+york|"
    r"chicago|denver|los\s+angeles|toronto|vancouver|singapore|hong\s+kong|tokyo|"
    r"india|indian)\s+(?:(?:eastern|central|western)\s+)?(?:standard\s+|daylight\s+)?time(?!-)|"
    # upper-case zone abbreviations; CST, EST, IST and BST often mean something else
    r"(?-i:AEST|AEDT|ACST|ACDT|AWST|NZST|NZDT|PST|PDT|EDT|CDT|MDT|CEST|JST|HKT|SGT)|"
    # an IANA zone such as Australia/Sydney, not a region pair such as Australia/NZ
    # or North America/Europe
    r"(?-i:(?<!Latin\s)(?<!North\s)(?<!South\s)(?<!Central\s)"
    r"(?:Africa|America|Asia|Australia|Europe|Pacific)/(?!(?:Africa|Americas?|"
    r"Asia|Australia|Europe|Latin|Middle|New|North|Oceania|Pacific|South)\b)"
    r"[A-Z][a-z]+(?:_[A-Z][a-z]+)*))\b",
    re.I,
)
# New rows in test fixtures, seed data, a test, dev, sandbox or local database, or
# Redis are a development count. A deploy, a migration, a cached report, test
# data, "fixture ads" or "home staging" can date or describe a business event,
# so those words alone do not silence the reminder: a missed reminder costs
# more than an extra one.
DEV_COUNT = re.compile(
    r"\b(?:(?:test|seed|db|database|data|json|ya?ml|sql)\s+fixtures?|"
    r"fixtures?\s+(?:data|files?|rows?|db|database)|fixtures/\w+|"
    r"seed(?:ed|ing)?\s+(?:script|data|file|rows?|db|database)s?|"
    r"seed(?:ed|ing)?\s+the\s+(?:db|database)|db:seed|"
    r"\w*seeds?\.(?:sql|rb|py|ts|js|ya?ml)|"
    r"(?:test|dev|development|sandbox|staging|local|ci|qa|preview)\s+"
    r"(?:db|database|env(?:ironment)?)|test\s+suite|(?:in|from)\s+(?:the\s+)?mock\s+data|"
    r"(?:in|from)\s+the\s+cache(?!\s+of\b)|sqlite|"
    r"redis\s+(?:cache|db|database|instance|keys?|server)|in\s+redis|"
    r"(?:in|on|to)\s+staging|staging\s+(?:server|site|instance)|unit\s+tests?|"
    r"(?:db|database|schema)\s+migrations?|migration\s+(?:files?|scripts?)|migrations/\w+)\b",
    re.I,
)
# A named code file or PR makes a count a code question. Unlike CONCRETE, a data
# file (.csv, .json, .sql) or ~/ path does not: exploring it first is the point.
# A .js name needs a path and a lower-case file name ("Next.js" and
# "React/Next.js" are products), and "PR 2026" is a year but "PR #2026" is not.
CODE_REFERENCE = re.compile(
    r"[\w/.\-]+\.(?:py|tsx?|rb|go|rs|java|kt|sh|ya?ml|toml)\b|"
    r"[\w.\-]*/(?:[\w.\-]*/)*(?-i:[a-z_])[\w\-]*\.jsx?\b|"
    r"(?-i:\bPR)(?:\s*#\s*\d+|\s*(?!(?:19|20)\d\d\b)\d+)",
    re.I,
)
SILENCE_SCAN_CHARS = 2000
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
    "comparison, currency, or source. If the data is available, inspect it first and "
    "quantify how each choice moves the answer. Then ask one short clarification with "
    "concrete options, limited to the choices that would change the answer, giving the "
    "figure each option produces when you have it. {question_guidance} If an "
    "approved metric catalogue is available, use it. If the user asks to proceed without "
    "clarifying, state the assumptions and label the result exploratory. This reminder is "
    "advisory: it does not verify a source or make a value canonical. Mute with "
    "`# analysis-ok` or `CC_SKIP_ANALYSIS=1`."
)


def is_ambiguous_new_count(prompt: str) -> bool:
    # The question and any definition come first. Signals past the opening are
    # ignored, so the later rows of a pasted file cannot silence the reminder and
    # regex time stays bounded. A token cut at the limit is dropped, so the cut
    # cannot create a signal ("PSTN" cut to "PST").
    head = prompt[:SILENCE_SCAN_CHARS]
    if len(prompt) > SILENCE_SCAN_CHARS:
        head = re.sub(r"\S*\Z", "", head)
    return bool(AMBIGUOUS_NEW_COUNT.match(prompt)) and not (
        DEFINED_COUNT.search(head)
        or DEV_COUNT.search(head)
        or CODE_REFERENCE.search(head)
    )


def is_ambiguous_business_question(prompt: str) -> bool:
    return is_ambiguous_new_count(prompt) or any(
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
    elif is_ambiguous_new_count(prompt):
        guidance = (
            "For new-customer counts, clarify what makes a customer new (first payment, "
            "sign-up or trial; whether returning or reactivated customers count), which "
            "test, internal, trial and merged accounts to exclude, the time zone and "
            "window edges, and whether to count accounts, people or rows (duplicates, "
            "blank dates)."
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
        payload = json.loads(read_hook_input(sys.stdin) or "{}")
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
