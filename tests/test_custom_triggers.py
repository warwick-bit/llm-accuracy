"""User-owned configuration through the shipped commands, not just a regex."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_accuracy_wiring import posix_only, run_hook


def config_file(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "user config's triggers.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@posix_only
@pytest.mark.parametrize(
    ("index", "family", "prompt", "expected"),
    [
        (2, "claim_fidelity", "Fix socket pressure in net.py.", "equal membership"),
        (0, "analysis", "Fix socket pressure in net.py.", "analysis contract"),
        (1, "fusion_evidence", "Fix socket pressure in net.py.", "FUSION EVIDENCE"),
    ],
)
def test_custom_phrases_override_builtin_suppressors(
    tmp_path, index, family, prompt, expected
):
    path = config_file(tmp_path, {"extra_triggers": {family: ["socket pressure"]}})
    controls = {"LLM_ACCURACY_CONFIG": str(path), "CC_CLAIM_FIDELITY_MODE": "targeted"}
    result = run_hook(
        "UserPromptSubmit", index, json.dumps({"prompt": prompt}), controls=controls
    )

    assert result.returncode == 0
    assert result.stderr == ""
    output = json.loads(result.stdout)
    assert set(output) == {"hookSpecificOutput"}
    assert expected in output["hookSpecificOutput"]["additionalContext"]
    assert "socket pressure" not in result.stdout
    assert str(path) not in result.stdout


@posix_only
@pytest.mark.parametrize(
    ("phrase", "prompt", "fires"),
    [
        ("socket pressure", "SOCKET\n  PRESSURE is high", True),
        ("trace", "Check the traces", False),
        ("trace", "Check trace_id", False),
        ("trace", "Check (trace)", True),
        ("net.py", "Inspect netXpy", False),
        ("net.py", "Inspect net.py", True),
        ("a.*b", "Inspect axxxb", False),
        ("a.*b", "Inspect a.*b", True),
        ("straße", "Check STRASSE", True),
    ],
)
def test_literal_casefolded_phrase_boundaries(tmp_path, phrase, prompt, fires):
    path = config_file(tmp_path, {"extra_triggers": {"claim_fidelity": [phrase]}})
    controls = {"LLM_ACCURACY_CONFIG": str(path), "CC_CLAIM_FIDELITY_MODE": "targeted"}
    result = run_hook(
        "UserPromptSubmit", 2, json.dumps({"prompt": prompt}), controls=controls
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert bool(result.stdout) is fires


@posix_only
@pytest.mark.parametrize(
    ("index", "family", "marker", "skip"),
    [
        (0, "analysis", "analysis-ok", "CC_SKIP_ANALYSIS"),
        (1, "fusion_evidence", "fusion-ok", "CC_SKIP_FUSION_EVIDENCE"),
        (2, "claim_fidelity", "fidelity-ok", "CC_SKIP_CLAIM_FIDELITY"),
    ],
)
def test_custom_triggers_never_override_bypasses(tmp_path, index, family, marker, skip):
    path = config_file(tmp_path, {"extra_triggers": {family: ["socket pressure"]}})
    controls = {"LLM_ACCURACY_CONFIG": str(path)}
    for prompt, additions in [
        (f"Socket pressure. # {marker}", {}),
        ("Socket pressure.", {skip: "1"}),
    ]:
        result = run_hook(
            "UserPromptSubmit",
            index,
            json.dumps({"prompt": prompt}),
            controls={**controls, **additions},
        )
        assert result.returncode == 0
        assert result.stdout == result.stderr == ""


@posix_only
@pytest.mark.parametrize("index", [0, 1, 2])
def test_invalid_config_preserves_builtin_checks_without_echoing_contents(
    tmp_path, index
):
    path = config_file(
        tmp_path, {"extra_triggers": {"private-invalid-key": ["private-value"]}}
    )
    prompts = [
        "Analyze customer retention.",
        "Why do database rows disagree?",
        "Does this prove causation?",
    ]
    result = run_hook(
        "UserPromptSubmit",
        index,
        json.dumps({"prompt": prompts[index]}),
        controls={"LLM_ACCURACY_CONFIG": str(path)},
    )

    assert result.returncode == 0
    assert result.stdout
    assert (
        result.stderr
        == "LLM Accuracy: invalid_config; built-in checks remain active.\n"
    )
    assert "private" not in result.stdout + result.stderr
    assert str(path) not in result.stdout + result.stderr


@posix_only
def test_default_config_path_and_additive_family_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    path = tmp_path / "llm-accuracy.json"
    path.write_text(
        json.dumps(
            {"schema_version": 1, "extra_triggers": {"analysis": ["socket pressure"]}}
        )
    )
    for index, fires in [(0, True), (1, False), (2, False)]:
        result = run_hook(
            "UserPromptSubmit",
            index,
            json.dumps({"prompt": "Socket pressure."}),
            controls={"CC_CLAIM_FIDELITY_MODE": "targeted"},
        )
        assert result.returncode == 0
        assert result.stderr == ""
        assert bool(result.stdout) is fires


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"schema_version": True},
        {"schema_version": 2},
        {"extra_triggers": []},
        {"extra_triggers": {"unknown": []}},
        {"extra_triggers": {"analysis": "trace"}},
        {"extra_triggers": {"analysis": [None]}},
        {"extra_triggers": {"analysis": ["  "]}},
        {"extra_triggers": {"analysis": ["*"]}},
        {"extra_triggers": {"analysis": ["x" * 121]}},
        {"extra_triggers": {"analysis": ["trace"] * 65}},
    ],
)
def test_config_rejects_invalid_or_unbounded_rules(payload):
    from accuracy_config import trigger_lists

    with pytest.raises(ValueError):
        trigger_lists(payload)


@pytest.mark.parametrize("kind", ["malformed", "oversized", "directory", "missing"])
def test_bad_config_inputs_fail_open_with_fixed_diagnostic(
    tmp_path, monkeypatch, capsys, kind
):
    from accuracy_config import read_triggers

    path = tmp_path / "config.json"
    if kind == "malformed":
        path.write_text('{"secret-placeholder":')
    elif kind == "oversized":
        path.write_text(" " * 32_769)
    elif kind == "directory":
        path.mkdir()
    monkeypatch.setenv("LLM_ACCURACY_CONFIG", str(path))

    assert read_triggers() == {}
    captured = capsys.readouterr()
    expected = "config_unavailable" if kind == "missing" else "invalid_config"
    assert captured.out == ""
    assert captured.err == f"LLM Accuracy: {expected}; built-in checks remain active.\n"


def test_config_rereads_changes_and_accepts_windows_utf8_bom(tmp_path, monkeypatch):
    from accuracy_config import custom_trigger_matches

    path = tmp_path / "config.json"
    monkeypatch.setenv("LLM_ACCURACY_CONFIG", str(path))
    path.write_text(
        json.dumps({"extra_triggers": {"claim_fidelity": ["socket pressure"]}}),
        encoding="utf-8-sig",
    )
    assert custom_trigger_matches("claim_fidelity", "Check socket pressure")
    path.write_text(json.dumps({"extra_triggers": {"claim_fidelity": []}}))
    assert not custom_trigger_matches("claim_fidelity", "Check socket pressure")


@posix_only
def test_empty_custom_list_does_not_remove_builtins(tmp_path):
    path = config_file(tmp_path, {"extra_triggers": {"claim_fidelity": []}})
    result = run_hook(
        "UserPromptSubmit", 2, json.dumps({"prompt": "Does this prove causation?"}),
        controls={"LLM_ACCURACY_CONFIG": str(path), "CC_CLAIM_FIDELITY_MODE": "targeted"},
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert "equal membership" in result.stdout


@posix_only
def test_general_mode_custom_phrase_adds_detailed_guidance(tmp_path):
    path = config_file(tmp_path, {"extra_triggers": {"claim_fidelity": ["socket pressure"]}})
    result = run_hook(
        "UserPromptSubmit", 2, json.dumps({"prompt": "Check socket pressure."}),
        controls={"LLM_ACCURACY_CONFIG": str(path)},
    )
    assert result.returncode == 0
    assert result.stderr == ""
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "competing causes" in context
    assert "equal membership" in context
    assert len(context) <= 2000


@pytest.mark.parametrize("script,family", [
    ("analysis-contract-injector.py", "analysis"),
    ("fusion-evidence-trigger.py", "fusion_evidence"),
    ("claim-fidelity-trigger.py", "claim_fidelity"),
])
def test_unicode_custom_trigger_uses_utf8_bytes(tmp_path, script, family):
    path = config_file(tmp_path, {"extra_triggers": {family: ["résumé"]}})
    hook = Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/hooks" / script
    env = {**os.environ, "LLM_ACCURACY_CONFIG": str(path),
           "CC_CLAIM_FIDELITY_MODE": "targeted", "PYTHONUTF8": "0",
           "PYTHONIOENCODING": "cp1252:surrogateescape"}
    result = subprocess.run([sys.executable, str(hook)],
                            input=json.dumps({"prompt": "résumé"}, ensure_ascii=False).encode("utf-8"),
                            capture_output=True, env=env, timeout=30)
    assert result.returncode == 0 and result.stderr == b""
    assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
