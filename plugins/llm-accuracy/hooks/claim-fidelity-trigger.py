#!/usr/bin/env python3
"""Add general evidence guidance once per session, plus targeted prompt guidance.

Session mode (the default) adds the static general reminder from SessionStart,
which runs on startup, resume, clear and compaction. Each prompt gets a short
clarification check plus any targeted evidence guidance. General mode restores the general
reminder on every prompt; targeted mode keeps only the triggered guidance.
Subprocess tests live in tests/test_accuracy_wiring.py.
No prompt or evidence is retained or echoed.
"""

from __future__ import annotations

import json
import os
import re
import sys

from hook_input import read_hook_input

from accuracy_config import claim_fidelity_mode, custom_trigger_matches


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

# Data cues: a markdown table, or several numbers next to a data/finance word.
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
NUMBER_RE = re.compile(r"(?<![\w.])[-+]?[$€£]?\d[\d,]*(?:\.\d+)?%?")
DATA_WORD_RE = re.compile(
    r"\b(?:revenue|sales|cost|costs|cogs|margin|profit|loss|budget|actual|variance|"
    r"expense|expenses|invoice|invoices|price|prices|forecast|growth|cagr|churn|"
    r"conversion|conversions|rate|rates|ratio|average|mean|median|total|totals|"
    r"percent|percentage|share|aud|usd|eur|gbp|currency|exchange|fx|cash|balance|"
    r"customers|orders|units|quarter|quarterly|annual|monthly|yoy|kpi|metric)\b",
    re.IGNORECASE,
)
MIN_DATA_NUMBERS = 3
SAVED_OUTPUT_RE = re.compile(
    r"(\b\w*report\w*_v\d"
    r"|\b(saved|versioned|earlier|previous|prior|revised|updated|corrected)\s+(\w+\s+){0,2}"
    r"(report|handover|spreadsheet)s?\b"
    r"|\b(report|handover|spreadsheet)\s+(\w+\s+){0,3}(v\d+|version\s*\d+)\b)",
    re.IGNORECASE,
)

VERIFY_REQUEST_RE = re.compile(
    r"\b(?:verify|fact[ -]?check|audit|check (?:this|that|your|my|the (?:figures|facts|claims|accuracy))|you said|you told me|"
    r"your (?:previous|earlier) answer|root cause|outage|incident|recovery|patch|"
    r"production (?:fix|deployment)|bug fix)\b", re.IGNORECASE,
)

# Pure creative/translation requests do not ask to verify mentioned words.
TRANSFORM_REQUEST_RE = re.compile(
    r"^\s*(?:please\s+)?(?:translate\b|(?:write|compose)\b.{0,50}\b(?:poem|haiku|song|story)\b)",
    re.IGNORECASE,
)
ADDED_CHECK_RE = re.compile(
    r"\b(?:and|also|then)\s+(?:also\s+)?(?:verify|audit|fact[ -]?check)\b|"
    r"\b(?:verify|audit|fact[ -]?check|check)\s+(?:the\s+)?(?:facts|figures|accuracy|claims)\b",
    re.IGNORECASE,
)

FIX_ACTION_RE = re.compile(r"\bfix(?:ing)?\b", re.IGNORECASE)
FIX_BEHAVIOR_RE = re.compile(r"\b(?:contract|failing|failure|bug|defect|regression)\b", re.IGNORECASE)

MAX_INPUT_CHARS = 1_000_000
# hooks.json passes this action to the SessionStart registration.
SESSION_START = "session-start"

TECHNICAL_FOOTER = (
    "Use this Checked / Gap / Next footer only for a technical incident diagnosis "
    "or a code-repair handover:\n"
    "\n---\n\n"
    "- **Checked:** actual checks or supplied evidence, with scope\n"
    "- **Gap:** remaining unknowns (or none)\n"
    "- **Next:** smallest useful check or action (or none)\n"
    "Supplied evidence is not a check you performed. Keep headline, body and footer "
    "consistent; a Gap cannot excuse a stronger claim above. Omit this footer from "
    "ordinary numerical answers, other factual audits, routine replies and creative requests. "
    "Include only material scope or uncertainty where it affects the requested conclusion."
)

GENERAL_CONTRACT = (
    "CLAIM FIDELITY CHECK: Identify what evidence establishes "
    "and what is missing. For material claims and intermediate assertions, "
    "check whether alternatives explain the same observation. If evidence cannot "
    "distinguish them, qualify or withhold the claim. State supported narrow facts "
    "plainly. Separate observations, hypotheses "
    "and unknowns. Check field, units, denominator, environment and version; "
    "all/none claims need coverage beyond previews, samples and truncated output. "
    "A tool call is not verification. Test competing causes before declaring "
    "a root cause. Corrections must revisit dependent conclusions; repeated "
    "reversals require rechecking the framing. Use llm-accuracy:verify "
    "for diagnosis, fix checks and data calculations; conventions do not settle an "
    "unresolved inclusion rule. For material ambiguity, use llm-accuracy:clarify "
    "and CALL interactive multiple-choice. Advisory, not verification."
)

LABEL = "CLAIM FIDELITY CHECK: "

CLARIFY_CONTRACT = (
    "CLARIFY CHECK: Before reporting a metric, check its definition, included records "
    "and required inputs. If an unresolved choice materially changes the answer, "
    "use llm-accuracy:clarify and CALL the available interactive multiple-choice "
    "question tool; prose options or showing both results do not resolve the choice. "
    "Reuse settled definitions. If the user requested alternatives or authorized "
    "assumptions, follow that request. Otherwise wait for the answer before dependent "
    "conclusions. Proceed directly when nothing material is unresolved."
)

CONTRACT = (
    LABEL + "Keep every load-bearing conclusion inside the observed "
    "source, subject, population, definition, grain, window, freshness and completeness. "
    "A successful read proves only what it returned. Equal counts or totals do not prove "
    "equal membership. A business timestamp does not prove pipeline completeness. A "
    "provisional label does not repair a method/execution mismatch. Preserve conflicts and "
    "unknowns, separate causal claims from measured associations, and name the smallest "
    "additional check needed for any material gap."
)


DATA_CONTRACT = (
    "DATA ANSWER CHECK: This prompt supplies figures. Before answering, call the Skill tool for llm-accuracy:verify. "
    "Recompute every figure you state from the supplied data. Before sending, reconcile "
    "every explanation and summary sentence (direction, cause, comparison, dates, "
    "favourable/unfavourable, typical value, and counts such as \"two of four are "
    "wrong\") with your own final numbers and the data. Give one clear headline and "
    "remove superseded working. When checking someone's analysis, give one verdict per "
    "claim and confirm the correct ones; write those verdicts before any overall "
    "summary, and make the summary match them."
)

SAVED_OUTPUT_CONTRACT = (
    "SAVED OUTPUT CHECK (required): this request creates or revises a saved factual "
    "report or versioned output. Your first action must be the Skill tool call for "
    "llm-accuracy:verify, before writing any file; follow it to check the "
    "saved file and every change or correction explanation against the sources."
)


def has_data_cues(prompt: str) -> bool:
    """Supplied figures: a markdown table, or several numbers with a data word."""
    if len(TABLE_ROW_RE.findall(prompt)) >= 2 and NUMBER_RE.search(prompt):
        return True
    if not DATA_WORD_RE.search(prompt):
        return False
    return len(NUMBER_RE.findall(prompt)) >= MIN_DATA_NUMBERS


def task_checks(prompt: str, targeted: bool | None = None) -> str:
    """One skill request, with only the applicable task reminders."""
    # Quoted words are transformation input, not additional task instructions.
    directives = re.sub(r'"[^"\r\n]*"|(?<!\w)\'[^\'\r\n]*\'|`[^`\r\n]*`', "", prompt)
    if TRANSFORM_REQUEST_RE.search(prompt) and not ADDED_CHECK_RE.search(directives):
        return ""
    saved = bool(SAVED_OUTPUT_RE.search(prompt))
    figures = has_data_cues(prompt)
    requested = bool(VERIFY_REQUEST_RE.search(prompt)) or (should_fire(prompt) if targeted is None else targeted)
    requested = requested or bool(FIX_ACTION_RE.search(prompt) and FIX_BEHAVIOR_RE.search(prompt))
    if not (saved or figures or requested):
        return ""
    checks = ["VERIFICATION CHECK (required): Before substantive work or an audit verdict, "
              "your first action must be the Skill tool call for llm-accuracy:verify. "
              "Apply the relevant checks while working and to the final output before delivery."]
    if figures:
        checks.append("DATA ANSWER CHECK: Recompute stated figures and reconcile explanations "
                      "with the final numbers. Give per-claim audit verdicts before any overall summary.")
    if saved:
        checks.append("SAVED OUTPUT CHECK: Check the actual saved file, history and correction "
                      "explanations against the sources; preserve valid earlier claims.")
    return " ".join(checks)


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


def context_for_session(mode: str) -> str:
    """Static guidance for a session start; a prompt bypass cannot reach it."""
    return GENERAL_CONTRACT + " " + TECHNICAL_FOOTER if mode == "session" else ""


def context_for_prompt(prompt: str, mode: str) -> str:
    """Choose bounded guidance without treating prompt text as configuration."""
    if not prompt.strip() or BYPASS_RE.search(prompt):
        return ""
    targeted = should_fire(prompt)
    base = _mode_context(prompt, mode, targeted)
    checks = task_checks(prompt, targeted)
    return " ".join(part for part in (base, checks) if part)


def _mode_context(prompt: str, mode: str, targeted: bool | None = None) -> str:
    targeted = should_fire(prompt) if targeted is None else targeted
    if mode == "session":
        targeted = CONTRACT + " " + TECHNICAL_FOOTER if targeted else ""
        return CLARIFY_CONTRACT + (" " + targeted if targeted else "")
    if mode != "general":
        return CONTRACT + " " + TECHNICAL_FOOTER if targeted else ""
    if targeted:
        # One label per reminder; the targeted contract follows the general one.
        return GENERAL_CONTRACT + " " + CONTRACT[len(LABEL) :] + " " + TECHNICAL_FOOTER
    return GENERAL_CONTRACT + " " + TECHNICAL_FOOTER


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("CC_SKIP_CLAIM_FIDELITY") == "1":
        return 0
    arguments = sys.argv[1:] if argv is None else argv
    try:
        mode, _ = claim_fidelity_mode()
        if arguments[:1] == [SESSION_START]:
            # Every SessionStart source gets the reminder: an injection does not
            # survive the next compaction, so it must return after each one.
            # The payload is drained but not needed, so it cannot suppress it.
            try:
                read_hook_input(sys.stdin, MAX_INPUT_CHARS + 1)
            except Exception:
                pass
            event, context = "SessionStart", context_for_session(mode)
        else:
            raw = read_hook_input(sys.stdin, MAX_INPUT_CHARS + 1)
            if len(raw) > MAX_INPUT_CHARS:
                return 0
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return 0
            prompt = payload.get("prompt")
            if not isinstance(prompt, str):
                return 0
            event, context = "UserPromptSubmit", context_for_prompt(prompt, mode)
        if not context:
            return 0
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event,
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
