"""Subprocess tests for the exact commands shipped by the accuracy plugin."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import hook_argv


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "llm-accuracy"
HOOK_CONFIG = PLUGIN_ROOT / "hooks" / "hooks.json"

EXPECTED_HANDLERS = {
    ("UserPromptSubmit", 0): (
        "analysis-contract-injector.py",
        "Checking llm-accuracy analysis contract",
    ),
    ("UserPromptSubmit", 1): (
        "fusion-evidence-trigger.py",
        "Checking llm-accuracy fusion evidence",
    ),
    ("UserPromptSubmit", 2): (
        "claim-fidelity-trigger.py",
        "Checking llm-accuracy claim fidelity",
    ),
    ("SessionStart", 0): (
        "post-compact-accuracy.py",
        "Checking llm-accuracy post-compaction accuracy",
    ),
    ("SessionStart", 1): (
        "claim-fidelity-trigger.py:session-start",
        "Checking llm-accuracy claim fidelity",
    ),
    ("PostToolUse", 0): (
        "partial-result-sentinel.py",
        "Checking llm-accuracy partial result signal",
    ),
}



def hook_handler(event: str, index: int) -> dict[str, object]:
    config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))["hooks"]
    matchers = config[event]
    hooks = matchers[index]["hooks"]
    assert len(hooks) == 1
    return hooks[0]


def clean_environment() -> dict[str, str]:
    """Return the ambient environment without accuracy hook control variables."""
    excluded = {
        "CC_SKIP_ANALYSIS",
        "CC_SKIP_FUSION_EVIDENCE",
        "CC_SKIP_CLAIM_FIDELITY",
        "CC_CLAIM_FIDELITY_MODE",
        "CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE",
        "CC_SKIP_PARTIAL_RESULT",
        "CLAUDE_PLUGIN_ROOT",
    }
    return {key: value for key, value in os.environ.items() if key not in excluded}


def run_hook(
    event: str,
    index: int,
    stdin_text: str,
    *,
    plugin_root: Path = PLUGIN_ROOT,
    controls: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one command exactly as Claude Code receives it from hooks.json."""
    environment = clean_environment()
    environment.update(controls or {})
    environment["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    command = hook_handler(event, index)["command"]
    assert isinstance(command, str)
    return subprocess.run(
        hook_argv(hook_handler(event, index), plugin_root) ,
        input=stdin_text,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )


def test_only_the_canonical_hook_manifest_is_shipped() -> None:
    assert HOOK_CONFIG.is_file()
    assert not (PLUGIN_ROOT / "hooks.json").exists()

    config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert set(config) == {"hooks"}
    assert set(config["hooks"]) == {"UserPromptSubmit", "SessionStart", "PostToolUse"}
    assert config["hooks"]["SessionStart"][0]["matcher"] == "compact"
    # No matcher: startup, resume, clear and compaction all restore the reminder.
    assert "matcher" not in config["hooks"]["SessionStart"][1]
    assert config["hooks"]["PostToolUse"][0]["matcher"] == "^(mcp__.*|Bash|Read)$"

    for key, (filename, status_message) in EXPECTED_HANDLERS.items():
        handler = hook_handler(*key)
        assert set(handler) == {"type", "command", "timeout", "statusMessage"}
        assert handler["type"] == "command"
        assert handler["timeout"] == 10
        assert handler["statusMessage"] == status_message
        assert "python-launcher.cmd" in handler["command"]
        assert "user_config" not in handler["command"]
        assert f'"{filename}"' in handler["command"]
        assert (PLUGIN_ROOT / "hooks" / filename.partition(":")[0]).is_file()


def test_commands_support_plugin_paths_with_spaces_and_apostrophes(
    tmp_path: Path,
) -> None:
    copied_plugin = tmp_path / "plugin root's copy"
    shutil.copytree(PLUGIN_ROOT, copied_plugin)
    prompt = "Analyze customer retention by cohort."

    result = run_hook(
        "UserPromptSubmit",
        0,
        json.dumps({"prompt": prompt}),
        plugin_root=copied_plugin,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert prompt not in result.stdout
    assert "analysis contract" in result.stdout


@pytest.mark.parametrize(("event", "index"), EXPECTED_HANDLERS)
def test_commands_fail_open_when_plugin_root_is_missing(
    event: str,
    index: int,
    tmp_path: Path,
) -> None:
    result = run_hook(
        event,
        index,
        "",
        plugin_root=tmp_path / "missing-plugin",
    )

    assert result.returncode == 0
    assert result.stdout == ""
    # A missing package can emit a shell diagnostic, but must never exit 2.
    assert "python-launcher.cmd" in result.stderr


@pytest.mark.parametrize(
    ("event", "index", "prompt", "expected_context"),
    [
        (
            "UserPromptSubmit",
            0,
            "Analyze customer retention by cohort. Unique analysis prompt.",
            "analysis contract",
        ),
        (
            "UserPromptSubmit",
            1,
            (
                "The CRM is stale and the data warehouse has missing rows. "
                "Reconcile this unique source conflict."
            ),
            "Source reconciliation",
        ),
        (
            "UserPromptSubmit",
            2,
            "Does this evidence prove the source is current and complete?",
            "CLAIM FIDELITY CHECK",
        ),
    ],
)
def test_user_prompt_commands_emit_context_without_echoing_the_prompt(
    event: str,
    index: int,
    prompt: str,
    expected_context: str,
) -> None:
    result = run_hook(event, index, json.dumps({"prompt": prompt}))

    assert result.returncode == 0
    assert result.stderr == ""
    assert prompt not in result.stdout
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "UserPromptSubmit"
    assert expected_context in output["additionalContext"]


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("stdin_text", ["", "{not json", '["not", "an", "object"]'])
def test_user_prompt_commands_fail_open_on_malformed_stdin(
    index: int, stdin_text: str
) -> None:
    result = run_hook("UserPromptSubmit", index, stdin_text)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


ORDINARY_PROMPTS = [
    "The editor stalls after login.",
    "Proceed with the investigation.",
    "Which explanation survives the latest test?",
    "Repair retry handling in src/transport.py.",
    "Are we finished with the patch?",
    "Draft an update for the service owner.",
    "The first diagnosis was wrong. Reconsider it.",
    "Hello!",
]
SESSION_SOURCES = ["startup", "resume", "clear", "compact", "fork", None]
GENERAL_ONLY = "environment and version"
TARGETED_ONLY = "equal membership"


def session_start(source: str | None, controls: dict[str, str] | None = None):
    payload = {"hook_event_name": "SessionStart"}
    if source is not None:
        payload["source"] = source
    return run_hook("SessionStart", 1, json.dumps(payload), controls=controls)


@pytest.mark.parametrize("prompt", ORDINARY_PROMPTS)
def test_general_fidelity_covers_technical_work_and_followups(prompt: str) -> None:
    result = run_hook(
        "UserPromptSubmit",
        2,
        json.dumps({"prompt": prompt}),
        controls={"CC_CLAIM_FIDELITY_MODE": "general"},
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert prompt not in result.stdout
    output = json.loads(result.stdout)
    assert set(output) == {"hookSpecificOutput"}  # no blocking decision
    assert_general_reminder(output["hookSpecificOutput"]["additionalContext"])


@pytest.mark.parametrize("prompt", ORDINARY_PROMPTS)
def test_default_session_mode_keeps_ordinary_prompts_silent(prompt: str) -> None:
    result = run_hook("UserPromptSubmit", 2, json.dumps({"prompt": prompt}))

    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("source", SESSION_SOURCES)
def test_default_session_start_adds_the_general_reminder(source) -> None:
    result = session_start(source)

    assert result.returncode == 0
    assert result.stderr == ""
    output = json.loads(result.stdout)
    assert set(output) == {"hookSpecificOutput"}  # no blocking decision
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert_general_reminder(context)
    assert TARGETED_ONLY not in context


@pytest.mark.parametrize(
    "stdin_text",
    ["", "{not json", '["not", "an", "object"]', "x" * 1_000_001,
     json.dumps({"hook_event_name": "SessionStart", "prompt": "Hi # fidelity-ok"})],
    ids=["empty", "malformed", "array", "oversized", "bypass-marker"],
)
def test_session_start_reminder_ignores_its_payload(stdin_text: str) -> None:
    result = run_hook("SessionStart", 1, stdin_text)

    assert result.returncode == 0
    assert result.stderr == ""
    assert GENERAL_ONLY in json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    ("controls", "emits"),
    [
        ({}, True),
        ({"CC_CLAIM_FIDELITY_MODE": "session"}, True),
        ({"CC_CLAIM_FIDELITY_MODE": " Session "}, True),
        ({"CC_CLAIM_FIDELITY_MODE": "typo"}, True),
        ({"CC_CLAIM_FIDELITY_MODE": "general"}, False),
        ({"CC_CLAIM_FIDELITY_MODE": "targeted"}, False),
        ({"CC_SKIP_CLAIM_FIDELITY": "1"}, False),
        ({"CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE": "general"}, False),
        ({"CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE": "targeted"}, False),
        ({"CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE": "typo"}, True),
        (
            {
                "CC_CLAIM_FIDELITY_MODE": "session",
                "CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE": "general",
            },
            True,
        ),
        (
            {
                "CC_CLAIM_FIDELITY_MODE": "  ",
                "CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE": "general",
            },
            False,
        ),
    ],
)
def test_session_start_reminder_follows_the_mode(
    controls: dict[str, str], emits: bool
) -> None:
    result = session_start("startup", controls)

    assert result.returncode == 0
    assert result.stderr == ""
    if emits:
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert_general_reminder(context)
    else:
        assert result.stdout == ""


def assert_general_reminder(context: str) -> None:
    assert context.count("CLAIM FIDELITY CHECK") == 1
    assert GENERAL_ONLY in context
    assert "previews, samples" in context
    assert "competing causes" in context
    assert "repeated reversals" in context
    assert "Checked / Gap / Next" in context
    assert "actual checks or supplied evidence, with scope" in context
    assert "including rejecting" in context
    assert context.count("- **Checked:** actual") == 1
    assert "footer:\n\n---\n\n- **Checked:**" in context
    assert "\n- **Gap:** remaining" in context
    assert "\n- **Next:** smallest" in context
    assert "Skip this footer for routine replies" in context
    assert len(context) <= 1500


ORDINARY = "Repair src/transport.py."
TRIGGERED = "Does this prove causation?"
OPTION = "CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE"


@pytest.mark.parametrize(
    ("prompt", "controls", "expected"),
    [
        # Default session mode: targeted guidance only; the baseline is at SessionStart.
        (ORDINARY, {}, None),
        (TRIGGERED, {}, "targeted"),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "typo"}, None),
        (TRIGGERED, {"CC_CLAIM_FIDELITY_MODE": "typo"}, "targeted"),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "general"}, "general"),
        (TRIGGERED, {"CC_CLAIM_FIDELITY_MODE": "general"}, "general+targeted"),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "targeted"}, None),
        (TRIGGERED, {"CC_CLAIM_FIDELITY_MODE": "targeted"}, "targeted"),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": " TARGETED "}, None),
        # The saved plugin option, and the environment variable's precedence.
        (ORDINARY, {OPTION: "general"}, "general"),
        (ORDINARY, {OPTION: " General "}, "general"),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "targeted", OPTION: "general"}, None),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "", OPTION: "general"}, "general"),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "typo", OPTION: "general"}, None),
        (ORDINARY, {"CC_CLAIM_FIDELITY_MODE": "general", OPTION: "session"}, "general"),
        # Mutes.
        (ORDINARY, {"CC_SKIP_CLAIM_FIDELITY": "1", "CC_CLAIM_FIDELITY_MODE": "general"}, None),
        (TRIGGERED, {"CC_SKIP_CLAIM_FIDELITY": "1"}, None),
        (TRIGGERED + " # fidelity-ok", {}, None),
        (TRIGGERED + " # Fidelity-OK", {}, None),
        (ORDINARY + " # fidelity-ok", {"CC_CLAIM_FIDELITY_MODE": "general"}, None),
        (TRIGGERED + " # fidelity-ok", {"CC_CLAIM_FIDELITY_MODE": "targeted"}, None),
    ],
)
def test_fidelity_modes_and_bypasses(
    prompt: str, controls: dict[str, str], expected: str | None
) -> None:
    result = run_hook(
        "UserPromptSubmit", 2, json.dumps({"prompt": prompt}), controls=controls
    )

    assert result.returncode == 0
    assert result.stderr == ""
    if expected is None:
        assert result.stdout == ""
        return
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert context.count("CLAIM FIDELITY CHECK") == 1
    assert "Checked:" in context
    assert "Gap:" in context
    assert "Next:" in context
    assert (GENERAL_ONLY in context) == expected.startswith("general")
    assert (TARGETED_ONLY in context) == expected.endswith("targeted")


@pytest.mark.parametrize(
    "payload",
    [{}, {"prompt": None}, {"prompt": 42}, {"prompt": []}, {"prompt": "  "},
     {"user_prompt": "Does this prove causation?"}],
)
def test_fidelity_is_silent_without_a_valid_documented_prompt(payload: dict) -> None:
    result = run_hook("UserPromptSubmit", 2, json.dumps(payload))

    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


def test_fidelity_input_budget_fails_open() -> None:
    result = run_hook("UserPromptSubmit", 2, json.dumps({"prompt": "x" * 1_000_001}))

    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


def test_session_start_compact_command_emits_the_freshness_nudge() -> None:
    result = run_hook("SessionStart", 0, json.dumps({"source": "compact"}))

    assert result.returncode == 0
    assert result.stderr == ""
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert "re-read exact values" in output["additionalContext"]


def test_session_start_command_is_silent_for_non_compact_sources() -> None:
    result = run_hook("SessionStart", 0, json.dumps({"source": "startup"}))

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


def blocks(body: object) -> list[dict]:
    """Wrap a body the way a Claude Code host delivers an MCP tool result.

    Observed live against a registered MCP server: `tool_response` is a bare
    list of content blocks whose text is the provider payload, not the provider
    object itself.
    """
    text = body if isinstance(body, str) else json.dumps(body)
    return [{"type": "text", "text": text}]


SENTINEL_END_TO_END_CASES = [
    ({"tool_name": "Read", "tool_response": {"type": "text", "file": {"startLine": 10, "numLines": 3, "totalLines": 31}}},
     "file_read_excerpt", "actual Read metadata fires"),
    ({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"},
      "tool_response": {"type": "text", "file": {"startLine": 1, "numLines": 2000, "totalLines": 3100}}},
     "file_read_excerpt", "a host cut on an unbounded Read fires"),
    ({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x", "offset": 10, "limit": 3},
      "tool_response": {"type": "text", "file": {"startLine": 10, "numLines": 3, "totalLines": 31}}},
     "", "a range the model requested stays silent"),
    ({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x", "limit": 5000},
      "tool_response": {"type": "text", "file": {"startLine": 1, "numLines": 2000, "totalLines": 3100}}},
     "file_read_excerpt", "a host cut below the requested limit fires"),
    ({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x", "offset": 3000, "limit": 500},
      "tool_response": {"type": "text", "file": {"startLine": 3000, "numLines": 101, "totalLines": 3100}}},
     "", "a requested range that reaches the end of the file stays silent"),
    ({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x", "offset": 10},
      "tool_response": {"type": "text", "file": {"startLine": 10, "numLines": 2000, "totalLines": 3100}}},
     "file_read_excerpt", "a host cut after an offset-only Read fires"),
    ({"tool_name": "Bash", "tool_response": {"stdout": "x" * 30, "persistedOutputPath": "/tmp/synthetic", "persistedOutputSize": 100}},
     "bash_output_excerpt", "actual Bash metadata fires"),
    ({"tool_name": "Bash", "tool_response": {"stdout": '{"has_more":true}', "has_more": True}},
     "", "Bash payload never enters the MCP detector"),
    (
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__slack__conversations_history",
            "tool_response": blocks(
                {
                    "ok": True,
                    "messages": [{"user": "U1", "text": "hello"}],
                    "has_more": True,
                    "response_metadata": {"next_cursor": "bmV4dDoxMjM"},
                }
            ),
        },
        "pagination_incomplete",
        "paginated provider response fires in the delivered shape",
    ),
    (
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__slack__conversations_history",
            "tool_response": blocks(
                {
                    "ok": True,
                    "messages": [{"user": "U1", "text": "hello"}],
                    "has_more": False,
                }
            ),
        },
        "",
        "complete provider response stays silent",
    ),
    (
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__db__query",
            "tool_response": blocks(
                {"rows": [{"feature": "paging", "has_more": True}]}
            ),
        },
        "",
        "business row named has_more stays silent",
    ),
    (
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__hubspot__get_properties",
            "tool_response": (
                "Error: result (94,455 characters across 1 line) exceeds maximum "
                "allowed tokens. Output has been saved to /tmp/tool-results/x.txt."
            ),
        },
        "truncated_result",
        "host over-budget notice fires",
    ),
    (
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__example__list_rows",
            "tool_response": {
                "structuredContent": {"rows": [{"id": 1}], "has_more": True}
            },
        },
        "pagination_incomplete",
        "MCP wire dict form still fires",
    ),
    (
        {"hook_event_name": "PostToolUse", "tool_name": "Bash"},
        "",
        "payload without a tool response stays silent",
    ),
]


def test_partial_result_sentinel_end_to_end_through_shipped_command() -> None:
    """Drive the exact hooks.json command through a shell, as the host does."""
    for payload, expected_code, label in SENTINEL_END_TO_END_CASES:
        result = run_hook("PostToolUse", 0, json.dumps(payload))

        assert result.returncode == 0, label
        assert result.stderr == "", label
        if expected_code:
            emitted = json.loads(result.stdout)
            hook_output = emitted["hookSpecificOutput"]
            assert hook_output["hookEventName"] == "PostToolUse", label
            assert expected_code in hook_output["additionalContext"], label
        else:
            assert result.stdout == "", label


def test_partial_result_sentinel_completes_within_its_declared_timeout() -> None:
    """Run the shipped command under the timeout the manifest actually declares.

    Drive large payloads through the shipped command under its declared budget:
    subprocess.run raises TimeoutExpired if the hook exceeds it. A prior audit
    measured 4.05s on a 50 MB payload, beyond the old three-second budget.
    """
    declared = hook_handler("PostToolUse", 0)["timeout"]
    assert isinstance(declared, int)
    assert declared == 10

    rows = [{"id": n, "name": f"row-{n}", "blob": "x" * 200} for n in range(20000)]
    payloads = [
        json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__example__list_rows",
                "tool_response": blocks({"rows": rows, "has_more": True}),
            }
        ),
        json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__example__wide",
                "tool_response": {f"field_{n}": n for n in range(300000)},
            }
        ),
    ]

    for payload in payloads:
        environment = clean_environment()
        environment["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
        command = hook_handler("PostToolUse", 0)["command"]
        assert isinstance(command, str)
        result = subprocess.run(
            hook_argv(hook_handler("PostToolUse", 0), PLUGIN_ROOT),
            input=payload,
            capture_output=True,
            text=True,
            env=environment,
            timeout=declared,
        )
        assert result.returncode == 0
        assert result.stderr == ""


def test_partial_result_sentinel_fails_safe_on_malformed_stdin() -> None:
    """A non-JSON payload must exit clean and silent rather than erroring."""
    result = run_hook("PostToolUse", 0, "not json at all")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_unicode_stdout_does_not_hide_persisted_output_gap():
    import sys

    hook = ROOT / "plugins/llm-accuracy/hooks/partial-result-sentinel.py"
    payload = {"tool_name": "Bash", "tool_response": {
        "stdout": "é", "stderr": "", "persistedOutputPath": "/synthetic/result",
        "persistedOutputSize": 4}}
    result = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True, timeout=30,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252:surrogateescape"},
    )
    assert result.returncode == 0 and result.stderr == b""
    assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def test_utf8_reader_preserves_character_budget_and_stream_ownership():
    import io
    from hook_input import read_hook_input

    binary = io.BytesIO("é".encode("utf-8") * 12)
    stream = io.TextIOWrapper(binary, encoding="cp1252")
    assert read_hook_input(stream, 5) == "é" * 5
    assert not binary.closed
    stream.close()


def test_utf8_reader_rejects_invalid_bytes_without_closing_stdin():
    import io
    from hook_input import read_hook_input

    binary = io.BytesIO(b"\xff")
    stream = io.TextIOWrapper(binary, encoding="cp1252")
    with pytest.raises(UnicodeDecodeError):
        read_hook_input(stream)
    assert not binary.closed
    stream.close()


@pytest.mark.parametrize("name", [
    "analysis-contract-injector.py", "fusion-evidence-trigger.py",
    "claim-fidelity-trigger.py", "partial-result-sentinel.py", "post-compact-accuracy.py",
])
def test_accuracy_hooks_fail_open_on_invalid_utf8_bytes(name):
    import sys

    hook = ROOT / "plugins/llm-accuracy/hooks" / name
    result = subprocess.run([sys.executable, str(hook)], input=b'{"prompt":"\xff"}',
                            capture_output=True, timeout=30)
    assert result.returncode == 0
    assert result.stdout == result.stderr == b""
