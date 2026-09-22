"""Synthetic safety, scoring and activation tests; no live model calls in CI."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

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
