"""Behaviour checks for the advisory hooks."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins" / "llm-accuracy" / "hooks"

ANALYSIS_FIRE_PROMPTS = [
    "Analyze churn by segment this quarter and tell me what's driving it.",
    "Break down revenue by cohort and explain the patterns.",
    "Find which customers have the strongest activation signals in our data.",
]

ANALYSIS_SILENT_PROMPTS = [
    "How many customers churned last week?",
    "Fix the CRM sync endpoint in app/api/crm.py.",
    "Investigate PR #164 for CI failures.",
    "Explore docs/plugin-maintenance.md.",
    "Analyze churn by segment. # analysis-ok",
    "Analyze churn by segment. # Analysis-OK",
]

FUSION_FIRE_PROMPTS = [
    (
        "What is this account's current MRR? Source A says $100, "
        "Source B says $130, and Source C is blank."
    ),
    (
        "How many enterprise leads converted last week? The CRM query returned "
        "HTTP 400 and the data warehouse returned zero rows because a join key "
        "was missing."
    ),
    (
        "Did this account ever pause? Current lifecycle says paying, while "
        "historical events say paused on April 10 and resumed May 1."
    ),
    (
        "Paste the account email and phone from the transcript. Metadata says "
        "identifiers are redacted and the permission row lacks support_pii.read."
    ),
    (
        "Which customers churned because of low usage? The data warehouse query "
        "returned LIMIT 100 capped rows and cancellation reason is null for many rows."
    ),
]

FUSION_SILENT_PROMPTS = [
    "Review this unified diff for bugs. It touches billing retry handling.",
    "Fix the CRM sync endpoint in app/api/crm.py.",
    "Analyze churn by segment this quarter.",
    "Forecast next month's MRR from the current pipeline.",
    "What is this account's current MRR?",
    "What is the current status?",
    "What is this account's current billing-system MRR?",
    "What is the current lifecycle in the CRM?",
    "Should we use Fusion for model benchmarking?",
    (
        "What is this account's current MRR? Source A says $100, "
        "Source B says $130. # fusion-ok"
    ),
    (
        "What is this account's current MRR? Source A says $100, "
        "Source B says $130. # Fusion-OK"
    ),
]


def load_hook(filename: str) -> ModuleType:
    path = HOOKS / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analysis_hook_precision_battery() -> None:
    hook = load_hook("analysis-contract-injector.py")

    for prompt in ANALYSIS_FIRE_PROMPTS:
        assert hook.should_fire(prompt), prompt
    for prompt in ANALYSIS_SILENT_PROMPTS:
        assert not hook.should_fire(prompt), prompt


def test_analysis_hook_emits_advisory_context(monkeypatch, capsys) -> None:
    hook = load_hook("analysis-contract-injector.py")
    monkeypatch.delenv("CC_SKIP_ANALYSIS", raising=False)
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"prompt": "Analyse customer retention by cohort."})),
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert (
        "analysis contract" in output["hookSpecificOutput"]["additionalContext"].lower()
    )


def test_fusion_hook_precision_battery() -> None:
    hook = load_hook("fusion-evidence-trigger.py")

    for prompt in FUSION_FIRE_PROMPTS:
        assert hook.should_fire(prompt), prompt
    for prompt in FUSION_SILENT_PROMPTS:
        assert not hook.should_fire(prompt), prompt


def test_fusion_hook_emits_advisory_context(monkeypatch, capsys) -> None:
    hook = load_hook("fusion-evidence-trigger.py")
    monkeypatch.delenv("CC_SKIP_FUSION_EVIDENCE", raising=False)
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "prompt": (
                        "The data warehouse is stale and the CRM has missing rows. "
                        "Can you reconcile the conflict?"
                    )
                }
            )
        ),
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert (
        "fusion evidence trigger"
        in output["hookSpecificOutput"]["additionalContext"].lower()
    )


def test_post_compact_hook_emits_freshness_nudge(monkeypatch, capsys) -> None:
    hook = load_hook("post-compact-accuracy.py")
    monkeypatch.setattr(
        hook.sys, "stdin", io.StringIO(json.dumps({"source": "compact"}))
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "re-read exact values" in output["hookSpecificOutput"]["additionalContext"]


def test_post_compact_hook_is_silent_for_non_compact_sources(
    monkeypatch, capsys
) -> None:
    hook = load_hook("post-compact-accuracy.py")
    monkeypatch.setattr(
        hook.sys, "stdin", io.StringIO(json.dumps({"source": "startup"}))
    )

    assert hook.main() == 0
    assert capsys.readouterr().out == ""
