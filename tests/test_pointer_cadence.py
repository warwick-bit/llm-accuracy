"""No-model checks for the Phase 2 pointer-cadence experiment's arms, fixture, trace and scoring."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import eval_pointer_cadence as pc  # noqa: E402


def registered(tree: Path, event: str) -> list[str]:
    hooks = json.loads((tree / "hooks/hooks.json").read_text())["hooks"]
    return [h["command"] for g in hooks.get(event, []) for h in g["hooks"]]


@pytest.fixture(scope="module")
def trees(tmp_path_factory):
    root = tmp_path_factory.mktemp("arms")
    return {arm: pc.build_arm(arm, root) for arm in pc.ARMS}


def test_arms_differ_only_in_pointer_cadence(trees):
    released = json.loads((pc.cadence.PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    released_prompt = [
        h["command"] for g in released["UserPromptSubmit"] for h in g["hooks"]
    ]
    for arm, tree in trees.items():
        prompt_cmds = registered(tree, "UserPromptSubmit")
        start_cmds = registered(tree, "SessionStart")
        assert prompt_cmds[: len(released_prompt)] == released_prompt
        assert sum(pc.cadence.BANNER_FILE in c for c in prompt_cmds) == 1
        pointer = (
            any(pc.POINTER_FILE in c for c in start_cmds),
            any(pc.POINTER_FILE in c for c in prompt_cmds),
        )
        assert (
            pointer
            == {
                "every_prompt": (True, True),
                "session_start": (True, False),
                "none": (False, False),
            }[arm]
        )


def test_session_start_pointer_matcher_covers_compaction(trees):
    for arm in ("every_prompt", "session_start"):
        hooks = json.loads((trees[arm] / "hooks/hooks.json").read_text())["hooks"]
        groups = [
            g
            for g in hooks["SessionStart"]
            if any(pc.POINTER_FILE in h["command"] for h in g["hooks"])
        ]
        assert [g["matcher"] for g in groups] == [pc.cadence.SESSION_MATCHER]


def run_pointer(tree: Path, payload: dict) -> str:
    result = subprocess.run(
        [sys.executable, str(tree / "hooks" / pc.POINTER_FILE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == payload["hook_event_name"]
    return out["additionalContext"]


def test_pointer_text_is_identical_at_both_events_and_names_the_session_registry(
    trees, tmp_path
):
    tree = trees["every_prompt"]
    start = run_pointer(tree, {"hook_event_name": "SessionStart", "cwd": str(tmp_path)})
    prompt = run_pointer(
        tree,
        {"hook_event_name": "UserPromptSubmit", "cwd": str(tmp_path), "prompt": "hi"},
    )
    assert (
        start
        == prompt
        == pc.POINTER_TEMPLATE.replace("{REGISTRY}", str(tmp_path / "metrics"))
    )
    assert pc.POINTER_MARK in start and "{REGISTRY}" not in start


def test_fixture_index_entries_and_aliases_agree(tmp_path):
    pc.write_fixture(tmp_path)
    index = (tmp_path / "metrics/index.md").read_text()
    tokens = [m[2] for m in pc.METRICS]
    assert len(set(tokens)) == len(tokens) == 6
    for key, aliases, token, *_ in pc.METRICS:
        entry = (tmp_path / "metrics" / f"{key}.md").read_text()
        assert "status: pinned" in entry and token in entry
        assert all(alias in index for alias in aliases)
    assert sorted(p.name for p in (tmp_path / "notes").iterdir()) == sorted(pc.NOTES)


def aliases_in(text: str) -> set[str]:
    lowered = text.lower()
    return {
        key
        for key, aliases, *_ in pc.METRICS
        if any(a.lower() in lowered for a in aliases)
    }


def test_scripts_probe_distinct_metrics_by_alias_and_filler_stays_clean():
    scripts = pc.build_scripts()
    assert set(scripts) == set(pc.CASES)
    for case, script in scripts.items():
        assert len(script) == len(pc.LAYOUT)
        keys = [k for _, k in script]
        assert [k is not None for k in keys] == [kind == "P" for kind in pc.LAYOUT]
        probe_keys = [k for k in keys if k]
        assert len(set(probe_keys)) == 3, case
        for prompt, key in script:
            if key:
                assert aliases_in(prompt) == {key}, prompt
                assert all(k not in prompt for k in pc.KEYS)
            else:
                assert aliases_in(prompt) == set(), prompt[:80]
                assert "metric" not in prompt.lower()
    for text in pc.NOTES.values():
        assert aliases_in(text) == set()


def stream(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


def use(use_id: str, path: str, name: str = "Read") -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": use_id,
                    "name": name,
                    "input": {"file_path": path},
                }
            ]
        },
    }


def outcome(use_id: str, error: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": use_id, "is_error": error}
            ]
        },
    }


def hook(text: str) -> dict:
    return {"type": "system", "subtype": "hook_response", "stdout": text}


def test_trace_segments_reads_by_turn_and_drops_failed_reads(tmp_path):
    work = tmp_path / "work"
    out = pc.trace(
        stream(
            hook(pc.POINTER_MARK + " " + pc.BANNER_MARK),
            use("a", str(work / "notes/x.md")),
            outcome("a"),
            {"type": "result", "result": "one"},
            hook(pc.FIDELITY_MARK),
            use("b", str(work / "metrics/index.md")),
            outcome("b"),
            use("c", "metrics/gross_bookings.md"),
            outcome("c", error=True),
            use("d", "/etc/hostname"),
            outcome("d"),
            {"type": "result", "result": "two"},
        )
    )
    assert out["marks"] == {"pointer": 1, "banner": 1, "fidelity": 1, "routing": 0}
    assert pc.relative_reads(out["turn_reads_abs"], work) == [
        ["notes/x.md"],
        ["<outside>", "metrics/index.md"],
    ]


def script_for(keys):
    return [(f"turn {i}", k) for i, k in enumerate(keys)]


def test_score_counts_an_entry_read_at_or_before_the_probe_and_flags_filler_reads():
    script = script_for(
        [
            None,
            "gross_bookings",
            None,
            None,
            "trial_conversion",
            None,
            None,
            "support_backlog",
        ]
    )
    reads = [
        [],
        ["metrics/gross_bookings.md", "metrics/index.md"],
        [],
        ["metrics/index.md"],
        [],
        ["metrics/support_backlog.md"],
        [],
        [],
    ]
    answers = ["", "from orders_ledger_v2", "", "", "", "", "", ""]
    marks = pc.expected_counts("session_start", 8)
    row = pc.score_session(
        {
            "status": "ok",
            "result_count": 8,
            "turn_reads": reads,
            "answers": answers,
            "marks": marks,
        },
        "session_start",
        script,
    )
    assert row["plumbing_ok"] and row["scorable"]
    assert row["per_turn"] == [False, True, False, True, False, True, False, True]
    assert (
        row["entry_read_this_turn"][1] is True
        and row["entry_read_this_turn"][7] is False
    )
    assert row["binding_cited"][1] is True and row["binding_cited"][4] is False


def test_plumbing_counts_and_unscorable_sessions():
    assert pc.expected_counts("every_prompt", 8)["pointer"] == 9
    assert pc.expected_counts("session_start", 8)["pointer"] == 1
    assert pc.expected_counts("none", 8)["pointer"] == 0
    row = pc.score_session(
        {"status": "timeout", "answers": []},
        "none",
        script_for([None, "gross_bookings"]),
    )
    assert not row["scorable"] and row["per_turn"] == []


def summary_row(arm, case, deep_hit, filler=False):
    keys = [
        None,
        "gross_bookings",
        None,
        None,
        "trial_conversion",
        None,
        None,
        "support_backlog",
    ]
    per_turn = [
        filler if k is None else (True if i == 1 else deep_hit)
        for i, k in enumerate(keys)
    ]
    return {
        "arm": arm,
        "case": case,
        "scorable": True,
        "plumbing_ok": True,
        "turns": {k: list(v) for k, v in pc.cadence.turn_sets(pc.LAYOUT).items()},
        "probe_keys": keys,
        "per_turn": per_turn,
        "entry_read_this_turn": [None if k is None else deep_hit for k in keys],
        "index_read_this_turn": [None if k is None else False for k in keys],
        "binding_cited": [None if k is None else deep_hit for k in keys],
    }


def test_summary_reuses_the_phase_one_rule_with_wilson_bounds():
    rows = [
        summary_row(
            arm,
            f"case_{i % 4}",
            {"every_prompt": True, "session_start": True, "none": False}[arm],
        )
        for i in range(12)
        for arm in pc.ARMS
    ]
    summary = pc.summarize(rows)
    assert summary["verdict"]["label"] == "every_prompt_redundant_for_retention"
    assert summary["arms"]["session_start"]["deep"]["wilson_lower_95"] == pytest.approx(
        0.8619, abs=1e-3
    )
    assert summary["arms"]["every_prompt"]["secondary"]["binding_cited"] == 36
    assert summary["arms"]["none"]["secondary"]["binding_cited"] == 0
    decayed = [
        {**r, "per_turn": [p if t != 7 else False for t, p in enumerate(r["per_turn"])]}
        if r["arm"] == "session_start"
        else r
        for r in rows
    ]
    assert pc.summarize(decayed)["verdict"]["label"] == "every_prompt_still_matters"


def test_stress_adds_the_routing_banner_to_every_arm_and_keeps_pointer_cadence(tmp_path):
    for arm in pc.ARMS:
        main = pc.build_arm(arm, tmp_path / "main")
        stress = pc.build_arm(arm, tmp_path / "stress", stress=True)
        main_prompt = registered(main, "UserPromptSubmit")
        stress_prompt = registered(stress, "UserPromptSubmit")
        assert [c for c in stress_prompt if pc.ROUTING_FILE not in c] == main_prompt
        assert sum(pc.ROUTING_FILE in c for c in stress_prompt) == 1
        assert registered(stress, "SessionStart") == registered(main, "SessionStart")
    assert pc.ROUTING_MARK in pc.ROUTING_TEXT
    assert pc.POINTER_MARK not in pc.ROUTING_TEXT and pc.BANNER_MARK not in pc.ROUTING_TEXT


def test_stress_fixture_adds_exports_and_names_them_as_known_wrong(tmp_path):
    main, stress = tmp_path / "main", tmp_path / "stress"
    pc.write_fixture(main)
    pc.write_fixture(stress, stress=True)
    assert not (main / "data").exists()
    assert sorted(p.name for p in (stress / "data").iterdir()) == sorted(pc.data_files())
    for key in pc.KEYS:
        assert pc.STRESS_AVOID not in (main / "metrics" / f"{key}.md").read_text()
        assert pc.STRESS_AVOID in (stress / "metrics" / f"{key}.md").read_text()
    assert pc.data_files() == pc.data_files()
    assert pc.expected_counts("session_start", 8, stress=True)["routing"] == 8


def test_data_read_without_entry_flags_the_5_sep_failure_signature():
    script = script_for([None, "gross_bookings", None, None, "trial_conversion"])
    reads = [[], ["data/orders.csv"], [], [], ["data/trials.csv", "metrics/trial_conversion.md"]]
    row = pc.score_session(
        {
            "status": "ok",
            "result_count": 5,
            "turn_reads": reads,
            "answers": [""] * 5,
            "marks": pc.expected_counts("none", 5, stress=True),
        },
        "none",
        script,
        stress=True,
    )
    assert row["plumbing_ok"]
    assert row["data_read_without_entry"] == [None, True, None, None, False]


def test_case_digest_ignores_case_selection_and_matches_full_run_receipts():
    import hashlib

    full = pc.build_scripts()
    expected = hashlib.sha256(json.dumps({c: full[c] for c in pc.CASES}).encode()).hexdigest()
    assert pc.cases_digest(False) == expected
    assert pc.cases_digest(True) != expected
