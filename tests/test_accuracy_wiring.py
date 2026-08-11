"""Subprocess tests for the exact commands shipped by the accuracy plugin."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


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
    os.name != "posix", reason="hook commands run through a POSIX shell"
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
) -> subprocess.CompletedProcess[str]:
    """Run one command exactly as Claude Code receives it from hooks.json."""
    environment = clean_environment()
    environment["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    command = hook_handler(event, index)["command"]
    assert isinstance(command, str)
    return subprocess.run(
        ["/bin/sh", "-c", command],
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
    assert config["hooks"]["PostToolUse"][0]["matcher"] == "mcp__.*"

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
@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("stdin_text", ["", "{not json", '["not", "an", "object"]'])
def test_user_prompt_commands_fail_open_on_malformed_stdin(
    index: int, stdin_text: str
) -> None:
    result = run_hook("UserPromptSubmit", index, stdin_text)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


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
def test_partial_result_sentinel_fails_safe_on_malformed_stdin() -> None:
    """A non-JSON payload must exit clean and silent rather than erroring."""
    result = run_hook("PostToolUse", 0, "not json at all")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
