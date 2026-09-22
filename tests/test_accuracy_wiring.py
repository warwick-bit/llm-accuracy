"""Subprocess tests for the exact commands shipped by the accuracy plugin."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import HOOK_SHELL


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
    ("PostToolUse", 0): (
        "partial-result-sentinel.py",
        "Checking llm-accuracy partial result signal",
    ),
}

posix_only = pytest.mark.skipif(
    not HOOK_SHELL, reason="requires a configured POSIX hook shell"
)


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
        [HOOK_SHELL, "-c", command],
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
    assert config["hooks"]["PostToolUse"][0]["matcher"] == "^(mcp__.*|Bash|Read)$"

    for key, (filename, status_message) in EXPECTED_HANDLERS.items():
        handler = hook_handler(*key)
        assert set(handler) == {"type", "command", "timeout", "statusMessage"}
        assert handler["type"] == "command"
        assert handler["timeout"] == 3
        assert handler["statusMessage"] == status_message
        assert filename in handler["command"]
        assert (PLUGIN_ROOT / "hooks" / filename).is_file()


@posix_only
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


@posix_only
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
    assert result.stderr == ""


@posix_only
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
            "FUSION EVIDENCE TRIGGER",
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


@posix_only
@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("stdin_text", ["", "{not json", '["not", "an", "object"]'])
def test_user_prompt_commands_fail_open_on_malformed_stdin(
    index: int, stdin_text: str
) -> None:
    result = run_hook("UserPromptSubmit", index, stdin_text)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


@posix_only
@pytest.mark.parametrize(
    "prompt",
    [
        "The editor stalls after login.",
        "Proceed with the investigation.",
        "Which explanation survives the latest test?",
        "Repair retry handling in src/transport.py.",
        "Are we finished with the patch?",
        "Draft an update for the service owner.",
        "The first diagnosis was wrong. Reconsider it.",
        "Hello!",
    ],
)
def test_general_fidelity_covers_technical_work_and_followups(prompt: str) -> None:
    result = run_hook("UserPromptSubmit", 2, json.dumps({"prompt": prompt}))

    assert result.returncode == 0
    assert result.stderr == ""
    assert prompt not in result.stdout
    output = json.loads(result.stdout)
    assert set(output) == {"hookSpecificOutput"}  # no blocking decision
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "process/environment and version" in context
    assert "previews, samples" in context
    assert "competing causes" in context
    assert "repeated reversals" in context
    assert "Checked / Gap / Next" in context
    assert "actual checks or supplied evidence, with scope" in context
    assert "including rejecting" in context
    assert context.count("Checked: actual") == 1
    assert "Skip this footer for routine replies" in context
    assert len(context) <= 1500


@posix_only
@pytest.mark.parametrize(
    ("prompt", "controls", "fires"),
    [
        ("Repair src/transport.py.", {"CC_CLAIM_FIDELITY_MODE": "targeted"}, False),
        ("Does this prove causation?", {"CC_CLAIM_FIDELITY_MODE": "targeted"}, True),
        ("Repair src/transport.py.", {"CC_CLAIM_FIDELITY_MODE": " TARGETED "}, False),
        ("Repair src/transport.py.", {"CC_CLAIM_FIDELITY_MODE": "typo"}, True),
        ("Repair src/transport.py.", {"CC_SKIP_CLAIM_FIDELITY": "1"}, False),
        ("Repair src/transport.py. # fidelity-ok", {}, False),
        ("Repair src/transport.py. # Fidelity-OK", {}, False),
        (
            "Does this prove causation? # fidelity-ok",
            {"CC_CLAIM_FIDELITY_MODE": "targeted"},
            False,
        ),
    ],
)
def test_fidelity_modes_and_bypasses(
    prompt: str, controls: dict[str, str], fires: bool
) -> None:
    result = run_hook(
        "UserPromptSubmit", 2, json.dumps({"prompt": prompt}), controls=controls
    )

    assert result.returncode == 0
    assert result.stderr == ""
    if fires:
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "CLAIM FIDELITY CHECK" in output["hookSpecificOutput"]["additionalContext"]
        assert "Checked / Gap / Next" in output["hookSpecificOutput"]["additionalContext"]
    else:
        assert result.stdout == ""


@posix_only
@pytest.mark.parametrize(
    "payload",
    [{}, {"prompt": None}, {"prompt": 42}, {"prompt": []}, {"prompt": "  "},
     {"user_prompt": "Does this prove causation?"}],
)
def test_fidelity_is_silent_without_a_valid_documented_prompt(payload: dict) -> None:
    result = run_hook("UserPromptSubmit", 2, json.dumps(payload))

    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@posix_only
def test_fidelity_input_budget_fails_open() -> None:
    result = run_hook("UserPromptSubmit", 2, json.dumps({"prompt": "x" * 1_000_001}))

    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@posix_only
def test_session_start_compact_command_emits_the_freshness_nudge() -> None:
    result = run_hook("SessionStart", 0, json.dumps({"source": "compact"}))

    assert result.returncode == 0
    assert result.stderr == ""
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert "re-read exact values" in output["additionalContext"]


@posix_only
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


@posix_only
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


@posix_only
def test_partial_result_sentinel_completes_within_its_declared_timeout() -> None:
    """Run the shipped command under the timeout the manifest actually declares.

    Other tests allow 10s, which cannot catch a regression that pushes the hook
    past its real budget. The third fresh audit measured 4.05s on a 50 MB
    payload, so the worst realistic inputs are driven here under the declared
    limit: subprocess.run raises TimeoutExpired if the budget is blown.
    """
    declared = hook_handler("PostToolUse", 0)["timeout"]
    assert isinstance(declared, int)
    assert declared == 3

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
            [HOOK_SHELL, "-c", command],
            input=payload,
            capture_output=True,
            text=True,
            env=environment,
            timeout=declared,
        )
        assert result.returncode == 0
        assert result.stderr == ""


@posix_only
def test_partial_result_sentinel_fails_safe_on_malformed_stdin() -> None:
    """A non-JSON payload must exit clean and silent rather than erroring."""
    result = run_hook("PostToolUse", 0, "not json at all")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
