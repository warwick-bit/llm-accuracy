"""Timeouts retain counters, never partial answers or raw diagnostic content."""

import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest


SPEC = importlib.util.spec_from_file_location(
    "timeout_probe",
    Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/scripts/host_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def delta(text):
    return {
        "type": "stream_event",
        "event": {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": text},
        },
    }


def test_timeout_reports_repetition_without_exposing_partial_text(tmp_path):
    sentinel = "PRIVATE_SYNTHETIC_LINE"
    events = [delta(sentinel + "\n"), delta((sentinel + "\n") * 19)]
    program = (
        "import json,sys,time\n"
        "sys.stdin.readline()\n"
        f"for event in {events!r}: print(json.dumps(event),flush=True)\n"
        "print('PRIVATE_STDERR',file=sys.stderr,flush=True)\n"
        "time.sleep(30)\n"
    )
    result = probe.communicate(
        [sys.executable, "-c", program], tmp_path, dict(os.environ), "input\n", 1
    )
    assert result["status"] == "timeout"
    assert result["answers"] == []
    assert result["progress"] == {
        "events_received": 2,
        "turns_sent": 1,
        "results_received": 0,
        "text_updates_received": 2,
        "text_characters_received": (len(sentinel) + 1) * 20,
        "non_whitespace_characters_received": len(sentinel) * 20,
        "most_repeated_nonempty_line_count": 20,
    }
    assert "PRIVATE" not in json.dumps(result)


def test_timeout_does_not_promote_a_completed_first_turn(tmp_path):
    program = (
        "import json,sys,time\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'type':'result','result':'PRIVATE_ANSWER'}),flush=True)\n"
        "sys.stdin.readline()\n"
        "time.sleep(30)\n"
    )
    result = probe.communicate(
        [sys.executable, "-c", program], tmp_path, dict(os.environ), "one\ntwo\n", 1
    )
    assert result["status"] == "timeout"
    assert result["answers"] == []
    assert result["progress"]["results_received"] == 1
    assert result["progress"]["turns_sent"] == 2
    assert "PRIVATE" not in json.dumps(result)


def test_completed_results_are_not_counted_twice_as_partial_answers(tmp_path):
    events = [delta("partial"), {"type": "result", "result": "final"}]
    program = (
        "import json,sys\nsys.stdin.readline()\n"
        f"for event in {events!r}: print(json.dumps(event),flush=True)\n"
    )
    result = probe.communicate(
        [sys.executable, "-c", program], tmp_path, dict(os.environ), "one\n", 5
    )
    assert result["status"] == "ok"
    assert result["answers"] == ["final"]
    assert result["result_count"] == 1


def test_response_limit_stops_owned_generator_and_never_scores(tmp_path, monkeypatch):
    child = []
    spawn = probe.subprocess.Popen

    def capture(*args, **kwargs):
        process = spawn(*args, **kwargs)
        child.append(process)
        return process

    monkeypatch.setattr(probe.subprocess, "Popen", capture)
    program = (
        "import json,sys,time\nsys.stdin.readline()\n"
        f"print(json.dumps({delta('PRIVATE_TEXT' * 20)!r}),flush=True)\n"
        "time.sleep(30)\n"
    )
    result = probe.communicate(
        [sys.executable, "-c", program],
        tmp_path,
        dict(os.environ),
        "one\n",
        5,
        max_response_chars=100,
    )
    assert result["status"] == "response_limit"
    assert result["answers"] == []
    assert result["progress"]["text_characters_received"] > 100
    assert child[0].poll() is not None
    assert "PRIVATE" not in json.dumps(result)


def test_response_budget_resets_per_turn_and_does_not_double_count_final_text():
    progress = probe.StreamProgress(max_response_chars=5)
    for _ in range(2):
        progress.observe(json.dumps(delta("12345")))
        progress.observe(json.dumps({"type": "result", "result": "12345"}))
    assert progress.snapshot()["text_characters_received"] == 10
    assert progress.snapshot()["results_received"] == 2
    with pytest.raises(probe.ResponseLimitExceeded):
        progress.observe(json.dumps(delta("123456")))


def test_final_only_output_cannot_bypass_response_budget():
    progress = probe.StreamProgress(max_response_chars=5)
    with pytest.raises(probe.ResponseLimitExceeded):
        progress.observe(json.dumps({"type": "result", "result": "123456"}))


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "100"])
def test_invalid_response_limit_does_not_launch(monkeypatch, limit):
    monkeypatch.setattr(
        probe.shutil, "which", lambda _: pytest.fail("must not discover CLI")
    )
    assert probe.run_probe(["synthetic"], None, max_response_chars=limit) == {
        "status": "invalid_response_limit",
        "answers": [],
    }


@pytest.mark.parametrize(
    "line",
    [
        "invalid",
        "[]",
        "null",
        '{"type":"stream_event","event":[]}',
        json.dumps(delta(None)),
        json.dumps(delta({"private": "value"})),
    ],
)
def test_malformed_events_do_not_escape_or_break_progress(line):
    progress = probe.StreamProgress()
    progress.observe(line)
    assert progress.snapshot()["text_characters_received"] == 0
    assert "private" not in json.dumps(progress.snapshot())


@pytest.mark.parametrize("limit", [None, 8000])
def test_probe_requests_partial_events_without_changing_model_or_prompt(
    monkeypatch, tmp_path, limit
):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(probe.shutil, "which", lambda _: "claude")
    captured = {}

    def communicate(command, cwd, env, stdin, timeout, **limits):
        captured.update(command=command, stdin=stdin, timeout=timeout, limits=limits)
        return {"status": "ok", "answers": ["OK"]}

    monkeypatch.setattr(probe, "communicate", communicate)
    probe.run_probe(
        ["synthetic"],
        None,
        model="opus",
        effort="medium",
        timeout=150,
        max_response_chars=limit,
    )
    command = captured["command"]
    assert "--include-partial-messages" in command
    assert command[command.index("--model") + 1] == "opus"
    assert command[command.index("--effort") + 1] == "medium"
    assert json.loads(captured["stdin"])["message"]["content"] == "synthetic"
    assert captured["timeout"] == 150
    assert captured["limits"] == (
        {} if limit is None else {"max_response_chars": limit}
    )
