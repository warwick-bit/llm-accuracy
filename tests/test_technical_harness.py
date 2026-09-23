"""Synthetic safety, scoring and activation tests; no live model calls in CI."""

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/llm-accuracy"


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN / "scripts"))
    import accuracy_doctor
    import host_probe

    spec = importlib.util.spec_from_file_location(
        "technical_eval", ROOT / "scripts/eval_technical_behavior.py"
    )
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    return accuracy_doctor, host_probe, evaluator


def result(answer, **updates):
    return {
        "status": "ok",
        "result_count": 1,
        "answers": [answer],
        "hook_response_count": 3,
        "fidelity_hook_responses": 1,
        **updates,
    }


@pytest.mark.parametrize(
    "answer,valid,passed",
    [
        ("Answer: no", True, True),
        ("**Answer:** no", True, True),
        ("**Answer:** **No.**", True, True),
        ("Answer: No.", True, True),
        ("- **Answer**: no", True, True),
        ("Answer: yes", True, False),
        ("Answer: not yes", False, False),
        ("The Answer: no", False, False),
        ("Answer: no\nAnswer: yes", False, False),
        ("Answer: no, probably", False, False),
    ],
)
def test_factual_oracle(modules, answer, valid, passed):
    scored = modules[2].score(result(answer), ["no"], 1, True, True)
    assert scored["factual_fields_valid"] == valid
    assert scored["factual_pass"] == passed


@pytest.mark.parametrize("value", ["20", "20.0", "020.00", "**20.000**"])
def test_numeric_value_equivalence(modules, value):
    scored = modules[2].score(result("Answer: " + value), ["20"], 1, True, True)
    assert scored["factual_fields_valid"]
    assert scored["factual_pass"]


@pytest.mark.parametrize("value", ["20.01", "19.999999999999999999999999999999"])
def test_numeric_value_difference_is_not_rounded_away(modules, value):
    assert not modules[2].score(result("Answer: " + value), ["20"], 1, True, True)[
        "factual_pass"
    ]


@pytest.mark.parametrize(
    "discovered,expected",
    [
        (r"C:\Windows\System32\bash.exe", None),
        (r"C:\Windows\Sysnative\bash.exe", None),
        (r"D:\Git\bin\bash.exe", r"D:\Git\bin\bash.exe"),
        (None, None),
    ],
)
def test_windows_shell_discovery_rejects_wsl_launcher(
    modules, tmp_path, monkeypatch, discovered, expected
):
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setattr(modules[0].shutil, "which", lambda name: discovered)
    assert modules[0].find_windows_shell() == expected


@pytest.mark.parametrize("exception", [KeyboardInterrupt, RuntimeError])
def test_probe_cleans_up_on_interruption_and_unexpected_errors(
    modules, tmp_path, monkeypatch, exception
):
    probe = modules[1]
    original_popen = probe.subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        return child

    def interrupt(*args):
        raise exception

    monkeypatch.setattr(probe.subprocess, "Popen", spawn)
    monkeypatch.setattr(probe, "_exchange", interrupt)
    try:
        with pytest.raises(exception):
            probe.communicate(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                tmp_path,
                dict(os.environ),
                "",
                5,
            )
        assert children[0].poll() is not None
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait()
            for name in ("stdin", "stdout", "stderr"):
                stream = getattr(child, name)
                if stream is not None:
                    stream.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX termination semantics")
def test_sigterm_cleans_up_probe_process_and_temporary_profile(tmp_path):
    ready = tmp_path / "ready.json"
    auth = tmp_path / "auth"
    auth.mkdir()
    (auth / ".credentials.json").write_text("{}")  # Synthetic, never real auth.
    child_code = (
        "import json,os,time; from pathlib import Path; "
        f"ready=Path({str(ready)!r}); pending=ready.with_suffix('.tmp'); "
        "pending.write_text(json.dumps({'pid':os.getpid(),"
        "'root':str(Path.cwd()),'auth_copy':"
        "(Path.cwd()/'profile/.credentials.json').is_file()})); "
        "pending.replace(ready); time.sleep(60)"
    )
    runner_code = (
        "import sys; "
        f"sys.path.insert(0, {str(PLUGIN / 'scripts')!r}); "
        "import host_probe; host_probe.shutil.which=lambda name:sys.executable; "
        "original=host_probe.communicate; "
        "host_probe.communicate=lambda command,cwd,env,stdin,timeout: "
        f"original([sys.executable,'-c',{child_code!r}],cwd,env,stdin,timeout); "
        "host_probe.run_probe(['synthetic'],None)"
    )
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(auth)}
    runner = subprocess.Popen([sys.executable, "-c", runner_code], env=env)
    record = None
    try:
        deadline = time.monotonic() + 5
        while not ready.is_file() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.is_file(), "owned child never started"
        record = json.loads(ready.read_text())
        assert record["auth_copy"]
        runner.send_signal(signal.SIGTERM)
        runner.wait(timeout=5)
        assert not Path(record["root"]).exists()
        with pytest.raises(ProcessLookupError):
            os.kill(record["pid"], 0)
    finally:
        if runner.poll() is None:
            runner.terminate()
            try:
                runner.wait(timeout=5)
            except subprocess.TimeoutExpired:
                runner.kill()
                runner.wait()
        if record:
            try:
                os.killpg(record["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
            import shutil

            shutil.rmtree(record["root"], ignore_errors=True)


def test_footer_cannot_rescue_wrong_fact(modules):
    answer = "Answer: yes\nChecked: complete\nGap: none\nNext: none"
    scored = modules[2].score(result(answer), ["no"], 1, True, True)
    assert scored["footer_present_all_turns"]
    assert not scored["factual_pass"]


def test_footer_mentions_and_overapplication(modules):
    evaluator = modules[2]
    assert not evaluator.labelled_values("We Checked: everything", "Checked")
    scored = evaluator.score(result("Hello\n**Checked:** nothing"), [], 1, False, True)
    assert scored["footer_overapplied"]
    assert scored["factual_pass"] is None


@pytest.mark.parametrize(
    "updates",
    [
        {"status": "authentication"},
        {"result_count": 0},
        {"answers": []},
        {"fidelity_hook_responses": 0},
    ],
)
def test_infrastructure_excluded_from_both_denominators(modules, updates):
    evaluator = modules[2]
    bad = evaluator.score(result("Answer: no", **updates), ["no"], 1, True, True)
    good = evaluator.score(result("Answer: no"), ["no"], 1, True, True)
    summary = evaluator.summarize([{"baseline": good, "candidate": bad}])
    assert summary["paired_cases"] == 0
    assert (
        summary["baseline"]["factual_cases"]
        == summary["candidate"]["factual_cases"]
        == 0
    )


def test_contaminated_baseline_is_unscored(modules):
    assert not modules[2].score(result("Answer: no"), ["no"], 1, True, False)[
        "scorable"
    ]


def test_host_parse_error_wins_over_plausible_answer(modules):
    payload = json.dumps({"type": "result", "is_error": True, "result": "Answer: no"})
    parsed = modules[1].parse_events(payload, "authentication expired", 0)
    assert parsed["status"] == "authentication"
    assert modules[1].parse_events("not-json", "", 0)["status"] == "missing_result"


def test_stream_turns_are_sequential_and_bounded(modules, tmp_path):
    program = "import sys,json\nfor line in sys.stdin:\n print(json.dumps({'type':'result','result':line.strip()}),flush=True)"
    value = modules[1].communicate(
        [sys.executable, "-c", program], tmp_path, dict(os.environ), "one\ntwo\n", 5
    )
    assert value["answers"] == ["one", "two"]
    sleepy = modules[1].communicate(
        [sys.executable, "-c", "import time;time.sleep(10)"],
        tmp_path,
        dict(os.environ),
        "one\n",
        0.1,
    )
    assert sleepy == {"status": "timeout", "answers": []}
    huge = modules[1].communicate(
        [sys.executable, "-c", "print('x'*4000001)"],
        tmp_path,
        dict(os.environ),
        "one\n",
        5,
    )
    assert huge["status"] == "oversized_output"


def test_doctor_never_echoes_config_or_manifest_contents(
    modules, tmp_path, monkeypatch
):
    doctor = modules[0]
    monkeypatch.setattr(doctor, "check_hooks", lambda *_: {"analysis": "emitted"})
    manifest = tmp_path / ".claude-plugin/plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"version": "private-needle"}))
    config = tmp_path / "bad.json"
    config.write_text("private-needle")
    monkeypatch.setenv("LLM_ACCURACY_CONFIG", str(config))
    report = doctor.diagnose(tmp_path)
    assert report["status"] == "attention"
    assert report["config_status"] == "invalid_config"
    assert "private-needle" not in json.dumps(report)
    assert report["current_session_activation"] == "unverified"


def test_inventory_filters_other_plugins_and_paths(modules, monkeypatch):
    doctor = modules[0]
    rows = [
        {
            "id": "llm-accuracy@test",
            "version": "0.6.0",
            "enabled": False,
            "installPath": "private-needle",
        },
        {"id": "private-needle@test", "version": "1.0.0", "enabled": True},
        {"id": "session-ledger@llm-accuracy", "enabled": True},
    ]
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "claude")
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, json.dumps(rows), ""),
    )
    report = doctor.installation_inventory()
    assert report == {
        "status": "listed",
        "plugin": "llm-accuracy",
        "installations": [{"version": "0.6.0", "enabled": False}],
    }


def test_disabled_hook_and_invalid_mode_visible(modules, monkeypatch):
    doctor = modules[0]
    monkeypatch.setenv("CC_SKIP_CLAIM_FIDELITY", "1")
    monkeypatch.setenv("CC_CLAIM_FIDELITY_MODE", "unknown-value")
    monkeypatch.setattr(doctor, "probe_command", lambda *a: "emitted")
    report = doctor.diagnose(shell="synthetic-shell")
    assert report["hook_commands"]["claim_fidelity"] == "disabled"
    assert not report["mode_recognized"]
    assert report["status"] == "attention"


@pytest.mark.parametrize(
    "tool,response,expected",
    [
        (
            "Read",
            {
                "type": "text",
                "file": {"startLine": 10, "numLines": 3, "totalLines": 31},
            },
            {"file_read_excerpt"},
        ),
        (
            "Read",
            {
                "type": "text",
                "file": {"startLine": 1, "numLines": 31, "totalLines": 31},
            },
            set(),
        ),
        (
            "Read",
            {
                "type": "text",
                "file": {"startLine": True, "numLines": 3, "totalLines": 31},
            },
            set(),
        ),
        (
            "Read",
            {
                "type": "image",
                "file": {"startLine": 10, "numLines": 3, "totalLines": 31},
            },
            set(),
        ),
        (
            "Read",
            {
                "type": "text",
                "file": {"startLine": 1, "numLines": -1, "totalLines": 31},
            },
            set(),
        ),
        (
            "Bash",
            {
                "stdout": "x" * 30,
                "persistedOutputPath": "/tmp/synthetic",
                "persistedOutputSize": 100,
            },
            {"bash_output_excerpt"},
        ),
        (
            "Bash",
            {
                "stdout": "é",
                "persistedOutputPath": "/tmp/synthetic",
                "persistedOutputSize": 2,
            },
            set(),
        ),
        ("Bash", {"stdout": '{"has_more":true}'}, set()),
        ("Bash", {"persistedOutputPath": "/tmp/synthetic"}, set()),
        ("Bash", None, set()),
        ("unknown", {"has_more": True}, set()),
    ],
)
def test_builtin_metadata_only(tool, response, expected):
    from builtin_result_signals import builtin_codes

    assert builtin_codes(tool, response) == expected


def test_builtin_corpus_reports_only_aggregate_counts(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import measure_builtin_result_corpus as corpus

    records = [
        {
            "message": {
                "content": [{"type": "tool_use", "name": "Read", "id": "synthetic-id"}]
            }
        },
        {
            "sessionId": "excluded",
            "toolUseResult": {"private-needle": True},
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": "synthetic-id"}]
            },
        },
        {
            "sessionId": "included",
            "toolUseResult": {
                "type": "text",
                "file": {
                    "startLine": 2,
                    "numLines": 1,
                    "totalLines": 3,
                    "content": "private-needle",
                },
            },
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": "synthetic-id"}]
            },
        },
    ]
    path = tmp_path / "synthetic.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records))
    report = corpus.measure([path], ["excluded"])
    assert report["Read"] == {
        "results": 1,
        "typed_metadata": 1,
        "candidate_firing": 1,
        "baseline_firing": 0,
    }
    assert "private-needle" not in json.dumps(report)


@pytest.mark.parametrize(
    "answer",
    [
        "Checked:\nGap: unknown\nNext: test",
        "Checked: supplied data\nGap:\nNext: test",
        "Checked: supplied data\nGap: unknown\nNext:",
        "Checked: supplied data\nGap: unknown",
        "Checked: supplied data\nNext: test\nGap: unknown",
        "Checked: supplied data\nGap: unknown\nNext: test\nChecked: repeated",
        "Checked: supplied data\nGap: unknown\nNext: test\nMore claims afterward.",
    ],
)
def test_footer_requires_nonempty_unique_terminal_order(modules, answer):
    assert not modules[2].footer_present(answer)


def test_footer_accepts_markdown_and_blank_line_separators(modules):
    assert modules[2].footer_present(
        "Conclusion.\n\n- **Checked:** supplied data\n\n- **Gap:** unknown\n\n- **Next:** test\n"
    )


def test_empty_answer_label_does_not_consume_next_line(modules):
    assert modules[2].labelled_values("Answer:\nno", "Answer") == [""]


def test_live_doctor_explains_legacy_counter(modules, monkeypatch, capsys):
    doctor = modules[0]
    monkeypatch.setattr(sys, "argv", ["doctor", "--live"])
    monkeypatch.setattr(doctor, "diagnose", lambda **kw: {"status": "ok"})
    monkeypatch.setattr(doctor, "installation_inventory", lambda: {"status": "listed"})
    monkeypatch.setattr(
        doctor, "run_probe", lambda *a, **kw: result("OK", builtin_signal_responses=0)
    )
    assert doctor.main() == 0
    live = json.loads(capsys.readouterr().out)["live"]
    explanation = live["counter_definitions"]["builtin_signal_responses"]
    assert "PARTIAL RESULT SIGNAL" in explanation
    assert "not keyword" in explanation
    assert "zero" in explanation
    assert "answers" not in live


@pytest.mark.parametrize("model", ["claude-opus-5-5", "unexpected-model"])
def test_natural_footer_comparison_requires_both_plugins_and_pinned_model(
    modules, monkeypatch, model
):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import eval_footer_behavior as natural

    roots = []

    def probe(prompts, plugin, **kwargs):
        roots.append(plugin)
        return result(
            "Checked: supplied evidence\nGap: environment\nNext: test",
            resolved_model=model,
        )

    monkeypatch.setattr(natural, "run_probe", probe)
    baseline = Path("synthetic-baseline")
    row = natural.compare_case(
        ("synthetic", ["Synthetic evidence?"], True), baseline, "claude-opus-5-5", 0
    )
    assert roots == [baseline, natural.PLUGIN]
    for arm in ("baseline", "candidate"):
        assert row[arm]["scorable"] == (model == "claude-opus-5-5")
        assert "factual_pass" not in row[arm]
        if model == "claude-opus-5-5":
            assert row[arm]["footer_present_all_turns"]
        else:
            assert "footer_present_all_turns" not in row[arm]


def test_natural_footer_never_scores_incomplete_pair(modules, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import eval_footer_behavior as natural

    monkeypatch.setattr(
        natural, "run_probe", lambda *a, **kw: {"status": "timeout", "answers": []}
    )
    monkeypatch.setattr(
        natural,
        "score",
        lambda *a, **kw: pytest.fail("incomplete pair must not reach scorer"),
    )
    row = natural.compare_case(
        ("synthetic", ["Question"], True), Path("baseline"), "claude-opus-5-5", 0, 2
    )
    assert row["transport_status"] == "transport_exhausted"
    assert len(row["transport_attempts"]) == 2
    assert not row["baseline"]["scorable"] and not row["candidate"]["scorable"]


@pytest.mark.parametrize("later_turn", [False, True])
def test_timeout_covers_blocked_stdin_delivery(modules, tmp_path, later_turn):
    import time

    program = "import time;time.sleep(5)"
    payload = "x" * 131072 + "\n"
    if later_turn:
        program = (
            "import sys,time,json\n"
            "sys.stdin.readline()\n"
            "print(json.dumps({'type':'result','result':'first'}),flush=True)\n"
            "time.sleep(5)"
        )
        payload = "first\n" + payload
    started = time.monotonic()
    result = modules[1].communicate(
        [sys.executable, "-c", program], tmp_path, dict(os.environ), payload, 0.2
    )
    assert result == {"status": "timeout", "answers": []}
    assert time.monotonic() - started < 3


def test_stream_input_uses_newline_framing_only(modules, tmp_path):
    program = "import sys,json\nfor line in sys.stdin:\n print(json.dumps({'type':'result','result':line.rstrip('\\n')}),flush=True)"
    result = modules[1].communicate(
        [sys.executable, "-X", "utf8", "-c", program],
        tmp_path,
        dict(os.environ),
        "a\u2028b\n",
        3,
    )
    assert result["answers"] == ["a\u2028b"]


def test_early_auth_error_survives_failed_later_input(modules, tmp_path):
    program = (
        "import sys,json\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'type':'result','is_error':True,'result':'authentication expired'}),flush=True)\n"
        "sys.exit(1)"
    )
    result = modules[1].communicate(
        [sys.executable, "-c", program],
        tmp_path,
        dict(os.environ),
        "first\n" + "x" * 131072 + "\n",
        3,
    )
    assert result["status"] == "authentication"


@pytest.mark.parametrize("noise", ["synthetic-429-marker", "authentication expired"])
def test_error_category_ignores_nonerror_event_content(modules, noise):
    events = [
        {"type": "system", "subtype": "init", "session_id": noise},
        {"type": "system", "subtype": "hook_response", "stdout": noise},
        {"type": "result", "result": noise},
        {
            "type": "result",
            "is_error": True,
            "result": "The model's tool call could not be parsed.",
            "session_id": noise,
        },
    ]
    payload = "\n".join(json.dumps(event) for event in events)
    assert modules[1].parse_events(payload, "", 0)["status"] == "host_error"


@pytest.mark.parametrize(
    "failure,expected",
    [
        ({"is_error": True, "result": "authentication expired"}, "authentication"),
        ({"is_error": True, "errors": ["HTTP 429: rate limit"]}, "rate_limit"),
        ({"subtype": "error_during_execution", "errors": ["login required"]}, "authentication"),
        ({"is_error": True, "errors": [None, 429, {"id": "login"}]}, "host_error"),
        ({"is_error": True, "result": 429, "errors": {"id": "login"}}, "host_error"),
        ({"is_error": True, "result": "Tool execution deadline expired"}, "host_error"),
        ({"is_error": True, "result": "OAuth token expired"}, "authentication"),
        ({"is_error": True, "result": "Failure on request 14290"}, "host_error"),
        ({"is_error": True, "result": "You hit your session limit; synthetic reset notice"}, "rate_limit"),
    ],
)
def test_error_category_uses_failed_result_fields(modules, failure, expected):
    payload = json.dumps({"type": "result", **failure})
    assert modules[1].parse_events(payload, "", 0)["status"] == expected


@pytest.mark.parametrize("stderr,expected", [("", "host_error"), ("rate limit", "rate_limit")])
def test_exit_error_does_not_classify_successful_answer(modules, stderr, expected):
    payload = json.dumps({"type": "result", "result": "Check whether authentication expired."})
    assert modules[1].parse_events(payload, stderr, 1)["status"] == expected


def test_kill_leaves_stdin_to_its_feeder(modules, tmp_path, monkeypatch):
    probe = modules[1]
    process = probe.subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(5)"],
        stdin=probe.subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    actual_stdin = process.stdin

    class FeederOwnedStream:
        def close(self):
            pytest.fail("caller must not race or block on feeder-owned stdin")

    process.stdin = FeederOwnedStream()
    process._accuracy_feeder_owned = True
    try:
        probe._kill(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        actual_stdin.close()
