"""No-model checks for the reminder-cadence experiment's arms, cases and decision rule."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import eval_reminder_cadence as cadence  # noqa: E402


def run_hook(script: Path, payload: dict) -> str:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CC_", "LLM_ACCURACY", "CLAUDE_PLUGIN_OPTION_"))
    }
    # Claude Code passes the harness's saved plugin options to hooks this way.
    for key, value in cadence.RECORDED_OPTIONS.items():
        env["CLAUDE_PLUGIN_OPTION_" + key.upper()] = value
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
        check=True,
    )
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def registered(tree: Path, event: str) -> list[str]:
    hooks = json.loads((tree / "hooks/hooks.json").read_text())["hooks"]
    return [h["command"] for g in hooks.get(event, []) for h in g["hooks"]]


@pytest.fixture(scope="module")
def trees(tmp_path_factory):
    root = tmp_path_factory.mktemp("arms")
    return {arm: cadence.build_arm(arm, root) for arm in cadence.ARMS}


def test_arms_differ_only_in_claim_fidelity_cadence(trees):
    for arm, tree in trees.items():
        prompt_cmds = registered(tree, "UserPromptSubmit")
        start_cmds = registered(tree, "SessionStart")
        assert sum(cadence.BANNER_FILE in c for c in prompt_cmds) == 1
        has_prompt = any(cadence.HOOK_FILE in c for c in prompt_cmds)
        has_start = any(cadence.SESSION_FILE in c for c in start_cmds)
        assert (has_prompt, has_start) == {
            "every_prompt": (True, False),
            "session_start": (False, True),
            "none": (False, False),
        }[arm]
    base = registered(trees["none"], "UserPromptSubmit")
    assert [
        c
        for c in registered(trees["every_prompt"], "UserPromptSubmit")
        if cadence.HOOK_FILE not in c
    ] == base


def test_arms_keep_the_recorded_release_conditions(trees):
    # The 0.8.0 SessionStart reminder would reach every arm, including none.
    for tree in trees.values():
        assert not any(
            cadence.HOOK_FILE in c for c in registered(tree, "SessionStart")
        )
    assert cadence.RECORDED_OPTIONS == {"claim_fidelity_mode": "general"}


def test_sessions_run_with_the_recorded_mode(monkeypatch, tmp_path):
    seen = {}

    def probe(prompts, tree, **options):
        seen.update(options)
        return {"status": "ok", "answers": []}

    monkeypatch.setattr(cadence, "run_probe", probe)
    cadence.run_one(("light_a", "none", 0, ["p"], tmp_path, "m", 1, None, False))
    assert seen["plugin_options"] == {"claim_fidelity_mode": "general"}


def test_session_start_matcher_covers_compaction(trees):
    hooks = json.loads((trees["session_start"] / "hooks/hooks.json").read_text())[
        "hooks"
    ]
    groups = [
        g
        for g in hooks["SessionStart"]
        if any(cadence.SESSION_FILE in h["command"] for h in g["hooks"])
    ]
    assert [g["matcher"] for g in groups] == [cadence.SESSION_MATCHER]


def test_session_start_text_is_byte_identical_to_per_prompt_text(trees):
    probe = cadence.PROBES[0]
    per_prompt = run_hook(
        trees["every_prompt"] / "hooks" / cadence.HOOK_FILE,
        {"hook_event_name": "UserPromptSubmit", "prompt": probe},
    )
    once = run_hook(
        trees["session_start"] / "hooks" / cadence.SESSION_FILE,
        {"hook_event_name": "SessionStart", "source": "startup"},
    )
    assert per_prompt and per_prompt == once
    assert "CLAIM FIDELITY CHECK" in once


def test_every_prompt_arm_injects_the_same_text_on_every_turn(trees):
    hook = trees["every_prompt"] / "hooks" / cadence.HOOK_FILE
    texts = {
        run_hook(hook, {"hook_event_name": "UserPromptSubmit", "prompt": p})
        for prompts in cadence.build_scripts().values()
        for p in prompts
    }
    assert len(texts) == 1


def test_no_case_prompt_fires_another_contract_hook(trees):
    hooks_dir = trees["none"] / "hooks"
    for prompts in cadence.build_scripts().values():
        for prompt in prompts:
            payload = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
            assert run_hook(hooks_dir / "fusion-evidence-trigger.py", payload) == ""
            assert run_hook(hooks_dir / "analysis-contract-injector.py", payload) == ""


def test_cases_and_banner_never_mention_the_footer():
    texts = [p for prompts in cadence.build_scripts().values() for p in prompts] + [
        cadence.BANNER_TEXT
    ]
    for text in texts:
        lowered = text.lower()
        assert "footer" not in lowered
        for label in ("checked:", "gap:", "next:"):
            assert label not in lowered


MAIN = ("light_a", "light_b", "heavy_a", "heavy_b")
STRESS = ("stress_a", "stress_b")


def test_scripts_shape_and_heavy_size():
    scripts = cadence.build_scripts()
    assert set(scripts) == set(MAIN) | set(STRESS)
    assert all(len(scripts[c]) == len(cadence.LAYOUT) for c in MAIN)
    probes = [scripts[c][t] for c in MAIN for t in cadence.PROBE_TURNS]
    assert sorted(probes) == sorted(cadence.PROBES)
    for case in ("heavy_a", "heavy_b"):
        filler = [scripts[case][t] for t in cadence.FILLER_TURNS]
        assert all(9_000 <= len(f) <= 16_000 for f in filler)


def test_stress_scripts_are_twenty_turns_with_deep_heavy_filler():
    scripts = cadence.build_scripts()
    sets = cadence.turn_sets(cadence.STRESS_LAYOUT)
    assert len(cadence.STRESS_LAYOUT) == 20
    assert sets["probe"] == (1, 10, 19) and sets["deep"] == (10, 19)
    probes = [scripts[c][t] for c in STRESS for t in sets["probe"]]
    assert sorted(probes) == sorted(cadence.STRESS_PROBES)
    for case in STRESS:
        filler = [scripts[case][t] for t in sets["filler"]]
        assert len(filler) == 17
        assert all(6_000 <= len(f) <= 11_000 for f in filler)
        assert sum(map(len, filler)) >= 120_000


def test_default_heavy_filler_is_unchanged_by_the_count_parameter():
    assert cadence.heavy_filler(3) == cadence.heavy_filler(3, 110)
    assert cadence.heavy_filler(3).count("## v4.") == 110


def stress_row(arm, case, deep_hits, filler=False):
    sets = cadence.turn_sets(cadence.STRESS_LAYOUT)
    footers = [filler] * 20
    footers[1] = True
    for turn, hit in zip(sets["deep"], deep_hits):
        footers[turn] = hit
    return {
        "arm": arm,
        "case": case,
        "scorable": True,
        "plumbing_ok": True,
        "footers": footers,
        "turns": {k: list(v) for k, v in sets.items()},
    }


def stress_rows(b_deep):
    rows = []
    for i in range(4):
        case = STRESS[i % 2]
        rows.append(stress_row("every_prompt", case, (True, True)))
        rows.append(stress_row("session_start", case, b_deep[i]))
        rows.append(stress_row("none", case, (False, False)))
    return rows


def test_stress_verdict_holds_decays_and_extends():
    holds = cadence.summarize(stress_rows([(True, True)] * 3 + [(True, False)]))
    assert holds["stress_verdict"]["label"] == "session_start_holds_at_depth"
    decays = cadence.summarize(
        stress_rows([(False, False), (True, False), (True, True), (True, True)])
    )
    assert decays["stress_verdict"]["label"] == "session_start_decays"
    extend = cadence.summarize(
        stress_rows([(True, False), (True, False), (True, True), (True, True)])
    )
    assert extend["stress_verdict"]["label"] == "extend"


def test_summary_uses_each_rows_recorded_turns():
    summary = cadence.summarize(stress_rows([(True, True)] * 4))
    assert summary["arms"]["session_start"]["deep"] == {"hits": 8, "n": 8, "rate": 1.0}
    assert summary["arms"]["none"]["turn_20"] == {"hits": 0, "n": 4}


def row(arm, case, footers, plumbing=True):
    return {
        "arm": arm,
        "case": case,
        "scorable": True,
        "plumbing_ok": plumbing,
        "footers": footers,
    }


def session(probe_hits: tuple[bool, bool, bool], filler: bool = False) -> list[bool]:
    footers = [filler] * len(cadence.LAYOUT)
    for turn, hit in zip(cadence.PROBE_TURNS, probe_hits):
        footers[turn] = hit
    return footers


def rows_for(a_deep_hit, b_deep_hit, c_deep_hit, per_arm=12, b_filler=False):
    out = []
    for i in range(per_arm):
        case = f"case_{i % 4}"
        out.append(row("every_prompt", case, session((True, True, a_deep_hit(i)))))
        out.append(
            row(
                "session_start",
                case,
                session((True, b_deep_hit(i), b_deep_hit(i)), b_filler),
            )
        )
        out.append(row("none", case, session((False, c_deep_hit(i), False))))
    return out


def test_verdict_redundant_when_session_start_matches():
    s = cadence.summarize(rows_for(lambda i: True, lambda i: True, lambda i: False))
    assert s["verdict"]["label"] == "every_prompt_redundant_for_retention"


def test_verdict_still_matters_when_session_start_decays():
    s = cadence.summarize(
        rows_for(lambda i: True, lambda i: i % 2 == 0, lambda i: False)
    )
    assert s["verdict"]["label"] == "every_prompt_still_matters"


def test_verdict_blocks_redundant_on_over_application():
    s = cadence.summarize(
        rows_for(lambda i: True, lambda i: True, lambda i: False, b_filler=True)
    )
    assert s["verdict"]["label"] != "every_prompt_redundant_for_retention"


def test_verdict_is_screen_below_minimum_and_non_discriminating_without_control_gap():
    small = cadence.summarize(
        rows_for(lambda i: True, lambda i: True, lambda i: False, per_arm=4)
    )
    assert small["verdict"]["label"] == "screen_only"
    flat = cadence.summarize(rows_for(lambda i: True, lambda i: True, lambda i: True))
    assert flat["verdict"]["label"] == "non_discriminating_redesign"


def test_plumbing_failures_are_excluded():
    rows = rows_for(lambda i: True, lambda i: True, lambda i: False)
    for r in rows:
        if r["arm"] == "session_start":
            r["plumbing_ok"] = False
    s = cadence.summarize(rows)
    assert s["arms"]["session_start"]["usable_sessions"] == 0
    assert s["verdict"]["label"] == "no_data"


def test_expected_fidelity_counts():
    assert cadence.expected_fidelity_responses("every_prompt", 8) == 8
    assert cadence.expected_fidelity_responses("session_start", 8) == 1
    assert cadence.expected_fidelity_responses("none", 8) == 0
