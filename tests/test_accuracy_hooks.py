"""Behaviour checks for the private-preview advisory hooks."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins" / "llm-accuracy" / "hooks"


def load_hook(filename: str) -> ModuleType:
    path = HOOKS / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analysis_hook_targets_analysis_but_not_simple_lookups() -> None:
    hook = load_hook("analysis-contract-injector.py")

    assert hook.should_fire("Analyse revenue trends by customer cohort.")
    assert not hook.should_fire("What is current revenue?")
    assert not hook.should_fire("Fix the revenue query in metrics.py.")


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
    assert "analysis contract" in output["hookSpecificOutput"]["additionalContext"].lower()


def test_fusion_hook_targets_source_conflicts_but_not_code_work() -> None:
    hook = load_hook("fusion-evidence-trigger.py")

    assert hook.should_fire(
        "The CRM has zero rows but the billing system differs. Please reconcile it."
    )
    assert not hook.should_fire("Fix fusion-evidence-trigger.py.")


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
    assert "fusion evidence trigger" in output["hookSpecificOutput"]["additionalContext"].lower()


def test_post_compact_hook_emits_freshness_nudge(capsys) -> None:
    hook = load_hook("post-compact-accuracy.py")

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "PostCompact"
    assert "re-read exact values" in output["hookSpecificOutput"]["additionalContext"]
