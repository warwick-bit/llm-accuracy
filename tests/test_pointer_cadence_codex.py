"""No-model checks for the Phase 3 Codex pointer-cadence driver: hook wiring, read parsing, scoring."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import eval_pointer_cadence as pc  # noqa: E402
import eval_pointer_cadence_codex as cx  # noqa: E402


def names(config: dict, event: str) -> list[str]:
    return [
        h["command"].split()[2]
        for g in config["hooks"].get(event, [])
        for h in g["hooks"]
    ]


@pytest.mark.parametrize("stress", [False, True])
def test_arms_differ_only_in_pointer_cadence(tmp_path, stress):
    base = ["analysis", "fusion", "fidelity", "banner"] + (
        ["routing"] if stress else []
    )
    for arm in pc.ARMS:
        config = cx.hooks_config(
            arm, tmp_path, tmp_path / "plugin", tmp_path / "log", stress
        )
        prompt, start = names(config, "UserPromptSubmit"), names(config, "SessionStart")
        assert prompt == base + (["pointer"] if arm == "every_prompt" else [])
        assert start == (["pointer"] if arm != "none" else [])
    with pytest.raises(ValueError):
        cx.hooks_config("weekly", tmp_path, tmp_path, tmp_path / "log", stress)


def run_hooks(home: Path, event: str, payload: dict) -> None:
    config = json.loads((home / "hooks.json").read_text())["hooks"]
    for group in config.get(event, []):
        for hook in group["hooks"]:
            subprocess.run(
                hook["command"],
                shell=True,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=30,
                check=True,
            )


@pytest.mark.parametrize("arm", pc.ARMS)
def test_codex_home_hooks_emit_and_log(tmp_path, monkeypatch, arm):
    monkeypatch.setattr(cx, "CODEX_AUTH", tmp_path / "absent-auth.json")
    layout = cx.session_layout(tmp_path, stress=False)
    work, home = layout["work"], layout["codex_home"]
    log = cx.build_codex_home(arm, layout, stress=False)
    assert not (home / "auth.json").exists()
    # The none arm carries no pointer text anywhere a session could find it.
    pointer = layout["harness"] / "experiment-hooks/pointer.py"
    assert pointer.exists() == (arm != "none")
    for source in ("startup", "resume"):
        run_hooks(
            home,
            "SessionStart",
            {"hook_event_name": "SessionStart", "source": source, "cwd": str(work)},
        )
    for _ in range(2):
        run_hooks(
            home,
            "UserPromptSubmit",
            {
                "hook_event_name": "UserPromptSubmit",
                "prompt": "How many paying customers do we have?",
                "cwd": str(work),
            },
        )
    marks, sources = cx.hook_marks(log)
    # Startup counts once, the harness resume never does: the same arithmetic as pc.expected_counts.
    assert marks == pc.expected_counts(arm, 2)
    if arm != "none":
        assert sources["pointer:SessionStart:resume:False"] == 1


def pointer_output(tmp_path: Path, payload: dict) -> dict:
    script = tmp_path / "pointer.py"
    script.write_text(
        cx.POINTER_SCRIPT.format(text=pc.POINTER_TEMPLATE.replace("{REGISTRY}", "/reg"))
    )
    out = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return json.loads(out)["hookSpecificOutput"]


def test_pointer_skips_only_the_resume_session_start(tmp_path):
    for source in ("startup", "clear", "compact"):
        text = pointer_output(
            tmp_path, {"hook_event_name": "SessionStart", "source": source}
        )["additionalContext"]
        assert pc.POINTER_MARK in text and "/reg/index.md" in text
    assert "additionalContext" not in pointer_output(
        tmp_path, {"hook_event_name": "SessionStart", "source": "resume"}
    )
    prompt = pointer_output(
        tmp_path, {"hook_event_name": "UserPromptSubmit", "prompt": "x"}
    )
    assert pc.POINTER_MARK in prompt["additionalContext"]
    assert prompt["hookEventName"] == "UserPromptSubmit"


ALL_METRICS = {"metrics/index.md", *[f"metrics/{k}.md" for k in pc.KEYS]}


@pytest.mark.parametrize(
    ("command", "stress", "reads", "whole"),
    [
        ("/bin/bash -lc 'cat metrics/index.md'", False, {"metrics/index.md"}, False),
        (
            'bash -lc "ls metrics && sed -n 1,40p metrics/active_subscribers.md"',
            False,
            {"metrics/active_subscribers.md"},
            False,
        ),
        ("/bin/bash -lc 'ls metrics'", False, set(), False),
        ("ls -la metrics/index.md", False, set(), False),
        ("FOO=1 find metrics -name '*.md'", False, set(), False),
        ("bash -lc 'cat metrics/*.md'", False, ALL_METRICS, True),
        ("bash -lc 'rg -n \"paying\" metrics/'", False, ALL_METRICS, True),
        ("bash -lc 'cd metrics && cat index.md'", False, {"metrics/index.md"}, False),
        (
            "bash -lc 'cat notes/standup-2026-09-30.md | head'",
            False,
            {"notes/standup-2026-09-30.md"},
            False,
        ),
        ("cat data/accounts.csv", False, set(), False),
        ("cat data/accounts.csv", True, {"data/accounts.csv"}, False),
        ("cat metrics/gross_bookings_v2.md", False, set(), False),
    ],
)
def test_command_reads(command, stress, reads, whole):
    assert cx.command_reads(command, stress) == (reads, whole)


def test_output_entries_match_entry_files_only():
    assert cx.output_entries(pc.index_text()) == set()
    for metric in pc.METRICS:
        assert cx.output_entries(pc.entry_text(metric)) == {metric[0]}
        assert cx.output_entries(pc.entry_text(metric, stress=True)) == {metric[0]}


def event(kind: str, **fields) -> str:
    return json.dumps({"type": kind, **fields})


def test_parse_turn_keeps_successful_reads_and_last_answer():
    entry = pc.entry_text(pc.METRICS[0])
    stdout = "\n".join(
        [
            "not json",
            "[1, 2]",
            event("thread.started", thread_id="th-1"),
            event(
                "item.completed",
                item={
                    "type": "command_execution",
                    "command": "bash -lc 'cat metrics/active_subscribers.md'",
                    "exit_code": 0,
                    "aggregated_output": entry,
                },
            ),
            event(
                "item.completed",
                item={
                    "type": "command_execution",
                    "command": "cat metrics/gross_bookings.md",
                    "exit_code": 1,
                    "aggregated_output": pc.entry_text(pc.METRICS[1]),
                },
            ),
            event("item.completed", item="oops"),
            event("item.completed", item={"type": "agent_message", "text": "draft"}),
            event("item.completed", item={"type": "agent_message", "text": "final"}),
            event("turn.completed", usage={}),
        ]
    )
    turn = cx.parse_turn(stdout, stress=False)
    assert turn["thread"] == "th-1" and turn["completed"]
    assert turn["answer"] == "final"
    assert turn["reads"] == ["metrics/active_subscribers.md"]
    assert turn["entries_in_output"] == ["active_subscribers"]
    assert (turn["commands"], turn["failed_commands"], turn["dir_reads"]) == (2, 1, 0)
    assert turn["output_present"]


def test_parse_turn_without_completion_is_not_completed():
    turn = cx.parse_turn(event("thread.started", thread_id="th-2"), stress=False)
    assert turn["thread"] == "th-2" and not turn["completed"] and turn["answer"] == ""


def test_hook_marks_counts_emitted_only(tmp_path):
    log = tmp_path / "log.jsonl"
    rows = [
        {
            "hook": "pointer",
            "event": "SessionStart",
            "source": "startup",
            "emitted": True,
        },
        {
            "hook": "pointer",
            "event": "SessionStart",
            "source": "resume",
            "emitted": False,
        },
        {
            "hook": "banner",
            "event": "UserPromptSubmit",
            "source": None,
            "emitted": True,
        },
        {"event": "UserPromptSubmit", "emitted": True},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\nbroken\n")
    marks, sources = cx.hook_marks(log)
    assert marks == {"pointer": 1, "banner": 1, "fidelity": 0, "routing": 0}
    assert sources["pointer:SessionStart:resume:False"] == 1
    assert cx.hook_marks(tmp_path / "missing.jsonl")[0] == {
        "pointer": 0,
        "banner": 0,
        "fidelity": 0,
        "routing": 0,
    }


def test_turn_command_isolates_the_profile_and_resumes_by_thread():
    first = cx.turn_command(Path("/x/codex"), "gpt-5.5", "xhigh", "hello", None)
    later = cx.turn_command(Path("/x/codex"), "gpt-5.5", "xhigh", "again", "th-1")
    assert first[0] == later[0] == "/x/codex"
    assert first[1:3] == ["exec", "--json"] and "resume" not in first
    assert later[1:3] == ["exec", "resume"] and later[-2:] == ["th-1", "again"]
    for command in (first, later):
        for flag in (
            "--ignore-user-config",
            "--ignore-rules",
            "--dangerously-bypass-hook-trust",
            'sandbox_mode="read-only"',
            'approval_policy="never"',
        ):
            assert flag in command


def test_output_audit_windows():
    script = [
        ("f", None),
        ("p", "active_subscribers"),
        ("f", None),
        ("p", "active_subscribers"),
    ]
    entries = [[], ["active_subscribers"], [], []]
    assert cx.output_audit(script, entries) == [False, True, False, True]
    assert cx.output_audit(script, [["gross_bookings"], [], [], []]) == [
        True,
        False,
        False,
        False,
    ]


@pytest.mark.parametrize("foreign", [{}, {"mcp_tool_call:notion.search": 1}])
def test_run_one_scores_script_turns_and_checks_canary_plumbing(monkeypatch, foreign):
    script = pc.build_scripts()["light_a"][:3]
    n = len(script)
    key = script[1][1]

    def fake_session(prompts, arm, model, effort, timeout, stress):
        assert prompts[-1] == cx.CANARY and len(prompts) == n + 1
        reads = [[], [f"metrics/{key}.md"], [], ["metrics/index.md"]]
        return {
            "status": "ok",
            "result_count": n + 1,
            "answers": [
                "a",
                f"uses {next(m[2] for m in pc.METRICS if m[0] == key)}",
                "c",
                "canary",
            ],
            "turn_reads": reads,
            "turn_entries_in_output": [[], [key], [], []],
            "output_present": True,
            "shown_commands": [[], [], [], []],
            "turn_seconds": [1.0] * (n + 1),
            "marks": pc.expected_counts("session_start", n + 1),
            "hook_sources": {},
            "commands": 2,
            "failed_commands": 0,
            "dir_reads": 0,
            "foreign_tools": foreign,
            "auth_refreshed": False,
            "resolved_model": "gpt-5.5",
        }

    monkeypatch.setattr(cx, "run_session", fake_session)
    row = cx.run_one(
        (
            "light_a",
            "session_start",
            0,
            script,
            "gpt-5.5",
            "xhigh",
            60,
            False,
            False,
            True,
        )
    )
    # Any connector or web tool call fails plumbing, whatever the hook counts say.
    assert row["scorable"] and row["plumbing_ok"] == (not foreign)
    assert row["foreign_tools"] == foreign
    assert len(row["per_turn"]) == n and row["per_turn"][1] is True
    assert row["binding_cited"][1] is True
    assert row["output_per_turn"] == [False, True, False]


FIXED_ENV = {
    "PATH",
    "HOME",
    "TMPDIR",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
    "CODEX_MANAGED_PACKAGE_ROOT",
    "CODEX_MANAGED_BY_NPM",
}


def test_session_env_is_an_allowlist(tmp_path):
    layout = cx.session_layout(tmp_path, stress=False)
    source = {
        "LANG": "C.UTF-8",
        "SOME_SERVICE_TOKEN": "t",
        "DATABASE_URL": "d",
        "PATH": "/host/bin",
    }
    env = cx.session_env(layout, tmp_path / "pkg", source)
    assert set(env) == FIXED_ENV | {"LANG"}
    assert env["HOME"] == str(layout["home"]) and "/host/bin" not in env["PATH"]


@pytest.mark.parametrize("stress", [False, True])
def test_registry_lives_outside_the_project(tmp_path, stress):
    layout = cx.session_layout(tmp_path, stress)
    work, registry = layout["work"], layout["registry"]
    assert not registry.is_relative_to(work) and not work.is_relative_to(registry)
    assert not (work / "metrics").exists() and (work / "notes").is_dir()
    assert (work / "data").is_dir() == stress
    assert sorted(p.name for p in registry.iterdir()) == sorted(
        cx.fixture_files(stress)["metrics"]
    )
    log = cx.build_codex_home("session_start", layout, stress)
    assert str(registry) in (log.parent / "experiment-hooks/pointer.py").read_text()


# Runs inside the sandbox; prints key names and booleans only, never a value.
PROBE = r"""
import json, os, sys
real_home, canary, work, registry, rc_name = sys.argv[1:6]
leaks = []
for pid in (p for p in os.listdir("/proc") if p.isdigit()):
    try:
        if canary.encode() in open(f"/proc/{pid}/environ", "rb").read():
            leaks.append(pid)
    except OSError:
        pass
try:
    open(os.path.join(work, "probe-write"), "w").close()
    work_writable = True
except OSError:
    work_writable = False
print(json.dumps({
    "env_keys": sorted(os.environ),
    "canary_in_env": any(canary in v for v in os.environ.values()),
    "proc_leaks": leaks,
    "pid_count": sum(p.isdigit() for p in os.listdir("/proc")),
    "host_home": sorted(os.listdir(real_home)) if os.path.isdir(real_home) else None,
    "shell_rc_exists": os.path.exists(os.path.join(real_home, rc_name)),
    "work_writable": work_writable,
    "work_readable": os.path.isfile(os.path.join(work, "notes", "standup-2026-09-30.md")),
    "registry_readable": os.path.isfile(os.path.join(registry, "index.md")),
}))
"""


def bwrap_works() -> bool:
    try:
        done = subprocess.run(
            ["bwrap", "--ro-bind", "/", "/", "true"], capture_output=True
        )
    except OSError:
        return False
    return done.returncode == 0


@pytest.mark.skipif(not bwrap_works(), reason="bwrap with user namespaces unavailable")
def test_isolated_session_cannot_see_host_env_proc_or_home(tmp_path, monkeypatch):
    canary = "cadence-host-canary-7f3a"
    monkeypatch.setenv("CADENCE_HOST_CANARY", canary)
    try:
        _, package = cx.native_codex()
    except RuntimeError:
        package = tmp_path / "pkg"
        package.mkdir()
    layout = cx.session_layout(tmp_path, stress=False)
    env = cx.session_env(layout, package, dict(os.environ))
    real_home = str(Path.home())
    probe_args = [
        real_home,
        canary,
        str(layout["work"]),
        str(layout["registry"]),
        ".bashrc",
    ]
    command = cx.isolated(
        [cx.HOOK_PYTHON, "-c", PROBE, *probe_args],
        env,
        tmp_path,
        layout["work"],
        package,
    )
    # A host process holding the canary in its exec-time environment: readable through /proc
    # unless the sandbox has its own PID namespace.
    host = subprocess.Popen(
        ["sleep", "60"], env={"PATH": "/usr/bin:/bin", "CADENCE_HOST_CANARY": canary}
    )
    try:
        out = subprocess.run(
            command, env=cx.launch_env(), capture_output=True, text=True, timeout=30, check=True
        ).stdout
    finally:
        host.kill()
        host.wait()
    seen = json.loads(out)
    # PWD is set by bwrap --chdir.
    assert set(seen["env_keys"]) <= FIXED_ENV | set(cx.ENV_ALLOW) | {"PWD"}
    assert not seen["canary_in_env"] and seen["proc_leaks"] == []
    assert seen["pid_count"] <= 3  # bwrap's PID 1 and the probe
    assert not seen["shell_rc_exists"] and seen["host_home"] in (None, [".nvm"])
    assert not seen["work_writable"]
    assert seen["work_readable"] and seen["registry_readable"]


@pytest.mark.skipif(not bwrap_works(), reason="bwrap with user namespaces unavailable")
def test_clearenv_alone_keeps_the_host_env_out(tmp_path, monkeypatch):
    """Second guard: even if bwrap were launched with the full host env, the session env stays clean."""
    canary = "cadence-host-canary-9c1d"
    monkeypatch.setenv("CADENCE_HOST_CANARY", canary)
    package = tmp_path / "pkg"
    package.mkdir()
    layout = cx.session_layout(tmp_path, stress=False)
    env = cx.session_env(layout, package, dict(os.environ))
    probe = "import json, os; print(json.dumps(sorted(os.environ)))"
    command = cx.isolated([cx.HOOK_PYTHON, "-c", probe], env, tmp_path, layout["work"], package)
    out = subprocess.run(command, env=dict(os.environ), capture_output=True, text=True, timeout=30, check=True)
    assert set(json.loads(out.stdout)) <= FIXED_ENV | set(cx.ENV_ALLOW) | {"PWD"}


def test_run_session_always_isolates_and_closes_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(cx, "CODEX_AUTH", tmp_path / "absent-auth.json")
    monkeypatch.setattr(cx, "native_codex", lambda: (tmp_path / "codex", tmp_path / "pkg"))
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        events = [{"type": "thread.started", "thread_id": "th-9"}, {"type": "turn.completed"}]
        return subprocess.CompletedProcess(command, 0, "\n".join(json.dumps(e) for e in events), "")

    monkeypatch.setattr(cx.subprocess, "run", fake_run)
    result = cx.run_session(["one", "two"], "none", "gpt-5.5", "low", 60, False)
    assert result["status"] == "ok" and result["result_count"] == 2
    for command, kwargs in calls:
        assert command[0] == "bwrap" and "--clearenv" in command
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["env"] == cx.launch_env()
    assert "resume" in calls[1][0] and calls[1][0][-2:] == ["th-9", "two"]


def test_parse_turn_counts_connector_and_web_tool_items():
    stdout = "\n".join(
        [
            event("thread.started", thread_id="th-3"),
            event("item.completed", item={"type": "mcp_tool_call", "server": "codex_apps", "tool": "notion_search"}),
            event("item.completed", item={"type": "mcp_tool_call", "server": "codex_apps", "tool": "notion_search"}),
            event("item.completed", item={"type": "web_search", "query": "x"}),
            event("item.completed", item={"type": "todo_list", "items": []}),
            event("turn.completed"),
        ]
    )
    turn = cx.parse_turn(stdout, stress=False)
    assert turn["foreign_tools"] == {"mcp_tool_call:codex_apps.notion_search": 2, "web_search:": 1}


def test_turn_command_disables_connectors_plugins_and_web_search():
    for thread in (None, "th-1"):
        command = cx.turn_command(Path("/x/codex"), "gpt-5.5", "xhigh", "p", thread)
        for flag in ("features.apps=false", "features.plugins=false", 'web_search="disabled"'):
            assert flag in command and command[command.index(flag) - 1] == "-c"
        assert command[-1] == "p"
