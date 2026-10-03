"""Opt-in native Read observation delivery smoke, never an accuracy benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/llm-accuracy"
sys.path.insert(0, str(PLUGIN / "scripts"))
from host_probe import CONTROL_VARS, _termination_cleanup, communicate  # noqa: E402


def observation_valid(value: object) -> bool:
    return value == {
        "schema_version": 1, "tool": "Read", "expected_path": True,
        "text_response": True, "content_matches_fixture": True,
        "authority": "tool_observation_only",
    }


def assess(result: dict, observation: object, source: str, marker: str, emit: bool) -> dict:
    """Check delivery using unpredictable markers, not factual answer quality."""
    answers = result.get("answers", [])
    completed = (
        result.get("status") == "ok" and result.get("result_count") == 1
        and len(answers) == 1 and isinstance(answers[0], str)
    )
    answer = answers[0] if completed else ""
    inventory = result.get("host_inventory", {})
    activation = (
        result.get("fidelity_hook_responses") == 1
        and inventory.get("status") == "reported"
        and inventory.get("accuracy_plugin_count") == 1
        and inventory.get("mcp_count") == 0
    )
    checks = {
        "completed": completed,
        "activation_observed": activation,
        "observation_valid": observation_valid(observation),
        "source_marker_returned": re.findall(r"^Source: (\S+)\s*$", answer, re.M) == [source],
        "observation_marker_as_expected": re.findall(r"^Observation: (\S+)\s*$", answer, re.M)
        == [marker if emit else "none"],
    }
    return {
        "passed": all(checks.values()), "checks": checks,
        "host_status": result.get("status", "unreported"),
        "resolved_model": result.get("resolved_model", "unreported"),
        "host_inventory": inventory,
    }


def prepare(root: Path, emit: bool) -> tuple[dict, str, str, dict]:
    """Keep profile, hook config, and receipts outside the allowed fixture cwd."""
    profile, workspace = root / "profile", root / "workspace"
    profile.mkdir(mode=0o700)
    workspace.mkdir()
    fixture = workspace / "sample.txt"
    source, marker = "source_" + secrets.token_hex(16), "observation_" + secrets.token_hex(16)
    content = "Synthetic fixture marker: " + source + "\n"
    fixture.write_text(content, encoding="utf-8")
    config = {
        "fixture": str(fixture), "content": content, "marker": marker,
        "emit": emit, "receipt": str(profile / "observation.json"),
    }
    config_path = profile / "observer.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    hook = shlex.join([sys.executable, str(ROOT / "scripts/capture_observation.py"), str(config_path)])
    settings = {
        "permissions": {
            "defaultMode": "dontAsk",
            "deny": ["Read(//" + str(profile).lstrip("/") + "/**)"],
        },
        "hooks": {
            event: [{"matcher": "*", "hooks": [{"type": "command", "command": hook, "timeout": 5}]}]
            for event in ("PreToolUse", "PostToolUse")
        },
    }
    (profile / "smoke-settings.json").write_text(json.dumps(settings), encoding="utf-8")
    prompt = (
        "Read sample.txt using the Read tool. Then report the fixture marker "
        "from the file and any Read observation marker supplied alongside the "
        "tool response. Use two plain lines: Source: <fixture marker> and "
        "Observation: <observation marker or none>."
    )
    return config, source, prompt, settings


def run_arm(emit: bool, model: str, effort: str, timeout: int) -> dict:
    executable = shutil.which("claude")
    if not executable:
        return {"passed": False, "host_status": "host_unavailable"}
    auth_root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    with tempfile.TemporaryDirectory(prefix="accuracy-capture-") as directory:
        root = Path(directory)
        config, source, prompt, _ = prepare(root, emit)
        profile = root / "profile"
        try:
            auth = auth_root / ".credentials.json"
            if auth.is_file():
                shutil.copyfile(auth, profile / auth.name)
                (profile / auth.name).chmod(0o600)
        except OSError:
            return {"passed": False, "host_status": "auth_copy_failed"}
        env = {k: v for k, v in os.environ.items() if k not in CONTROL_VARS}
        env["CLAUDE_CONFIG_DIR"] = str(profile)
        command = [
            executable, "--print", "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose", "--include-hook-events",
            "--setting-sources", "", "--settings", str(profile / "smoke-settings.json"),
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--tools", "Read", "--permission-mode", "dontAsk",
            "--disable-slash-commands", "--no-session-persistence",
            "--plugin-dir", str(PLUGIN), "--model", model, "--effort", effort,
            "--max-budget-usd", "1.00",
        ]
        stdin = json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n"
        start = time.monotonic()
        result = communicate(command, root / "workspace", env, stdin, timeout)
        try:
            observation = json.loads(Path(config["receipt"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            observation = None
        receipt = assess(result, observation, source, config["marker"], emit)
        receipt["elapsed_seconds"] = round(time.monotonic() - start, 1)
        receipt["profile_jsonl_files"] = len(list(profile.rglob("*.jsonl")))
        receipt["passed"] = receipt["passed"] and receipt["profile_jsonl_files"] == 0
    receipt["temporary_directory_removed"] = not root.exists()
    receipt["passed"] = receipt["passed"] and receipt["temporary_directory_removed"]
    return receipt


def summarize(arms: dict) -> dict:
    models = [arm.get("resolved_model", "unreported") for arm in arms.values()]
    matched = len(models) == 2 and models[0] != "unreported" and len(set(models)) == 1
    return {
        "scope": "synthetic_read_observation_delivery_only",
        "passed": matched and all(arm["passed"] for arm in arms.values()),
        "models_matched": matched,
        "accuracy_effect": "not_measured",
        "variance": "not_measured_one_attempt_per_arm",
        "arms": arms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("live smoke currently supports POSIX hosts only")
    if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]{1,100}", args.model) or not 1 <= args.timeout <= 240:
        parser.error("invalid model or timeout")
    arms = {}
    with _termination_cleanup():
        for name, emit in (("silent_control", False), ("observation_context", True)):
            arms[name] = run_arm(emit, args.model, args.effort, args.timeout)
            print(json.dumps({"arm": name, **arms[name]}), flush=True)
            if not arms[name]["passed"]:
                break
    summary = summarize(arms)
    summary["requested_model"] = args.model
    summary["effort"] = args.effort
    summary["source_hashes"] = {
        name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
        for name in ("capture_observation.py", "evidence_capture_smoke.py")
    }
    print(json.dumps(summary), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
