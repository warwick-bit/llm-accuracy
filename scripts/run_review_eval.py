#!/usr/bin/env python3
"""Opt-in synthetic Claude review comparison; persist only typed measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from review_eval_cases import cases, score


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "llm-accuracy"
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["supported", "needs_correction", "insufficient_evidence"]},
        "value": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "checks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "value", "reason", "checks"],
    "additionalProperties": False,
}


def body(path: Path) -> str:
    text = path.read_text()
    return text.split("---", 2)[2].strip() if text.startswith("---") else text


def instructions() -> dict[str, str]:
    candidate = body(PLUGIN / "skills/analytical-review/SKILL.md").replace("$ARGUMENTS", "the supplied review artifact")
    audit = "\n\n".join(body(PLUGIN / path) for path in (
        "skills/claim-fidelity/SKILL.md", "skills/self-audit/SKILL.md",
        "references/evidence-discipline.md"))
    placebo = ("Review the supplied work carefully. Consider its explanation and provide "
               "a useful, clear, concise review. Take the time needed to assess the "
               "material and explain your conclusions. ")
    words = (placebo * (len(candidate.split()) // len(placebo.split()) + 1)).split()
    return {"default": "Review the supplied work for correctness.", "audit": audit,
            "reviewer": candidate, "placebo": " ".join(words[:len(candidate.split())])}


def clean_environment(work: Path) -> dict[str, str]:
    """Use an auth-only profile; never read credential contents or inherit paid routes."""
    config = work / "config"
    config.mkdir(mode=0o700)
    source = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    credential = source / ".credentials.json"
    if not credential.is_file():
        raise RuntimeError("file_based_subscription_auth_unavailable")
    shutil.copyfile(credential, config / ".credentials.json")
    (config / ".credentials.json").chmod(0o600)
    environment = {key: os.environ[key] for key in (
        "PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR") if key in os.environ}
    environment.update({"HOME": str(work), "CLAUDE_CONFIG_DIR": str(config),
                        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                        "DISABLE_AUTOUPDATER": "1"})
    return environment


def communicate(command: list[str], prompt: str, cwd: Path,
                environment: dict[str, str], timeout: int) -> tuple[int, str, str]:
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, cwd=cwd,
                               env=environment, start_new_session=True)
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
        return process.returncode, stdout, stderr
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise


def decode_answer(stdout: str, validator=None) -> tuple[dict, list[str]]:
    response = json.loads(stdout)
    if response.get("is_error") or response.get("type") != "result":
        raise ValueError("model_error")
    answer = response.get("structured_output")
    if not isinstance(answer, dict):
        text = response.get("result", "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        answer = json.loads(text)
    if validator is not None:
        validator(answer)
        return answer, list(response.get("modelUsage", {}))
    if (set(answer) != set(SCHEMA["required"])
            or answer["verdict"] not in SCHEMA["properties"]["verdict"]["enum"]
            or not isinstance(answer["reason"], str)
            or not answer["reason"].strip()
            or (answer["value"] is not None and not isinstance(answer["value"], str))
            or not isinstance(answer["checks"], list)
            or any(not isinstance(check, str) for check in answer["checks"])):
        raise ValueError("invalid_answer_shape")
    return answer, list(response.get("modelUsage", {}))


def decode_stream(stdout: str, allowed_plugins: set[str], validator=None) -> tuple[dict, list[str], list[str]]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    initial = [event for event in events if event.get("type") == "system" and event.get("subtype") == "init"]
    results = [event for event in events if event.get("type") == "result"]
    if len(initial) != 1 or len(results) != 1:
        raise ValueError("missing_runtime_attestation")
    tool_names = initial[0].get("tools", [])
    expected = {"mcp__review__evidence", "mcp__review__query", "mcp__review__calculate"}
    if not expected <= set(tool_names) or set(tool_names) - expected - {"StructuredOutput"}:
        raise ValueError("unexpected_tool_inventory")
    names = {plugin.get("name", "unknown") for plugin in initial[0].get("plugins", [])}
    if names - allowed_plugins:
        raise ValueError("unexpected_plugin")
    answer, models = decode_answer(json.dumps(results[0]), validator)
    return answer, models, tool_names


def run_one(item: dict, arm: str, instruction: str, args: argparse.Namespace) -> dict:
    started = time.monotonic()
    record = {"case": item["id"], "domain": item["domain"], "arm": arm,
              "repeat": args.current_repeat, "status": "process_failure"}
    with tempfile.TemporaryDirectory(prefix="review-eval-") as directory:
        work = Path(directory)
        work.chmod(0o700)
        (work / "fixture.json").write_text(json.dumps(item["fixture"]))
        shutil.copyfile(ROOT / "scripts/review_eval_tools.py", work / "tools.py")
        trace = work / "trace.jsonl"
        mcp = {"mcpServers": {"review": {"command": sys.executable,
               "args": [str(work / "tools.py"), str(work / "fixture.json"), str(trace)]}}}
        (work / "mcp.json").write_text(json.dumps(mcp))
        command = [args.claude_binary, "--print", "--no-session-persistence",
                   "--model", args.model, "--effort", args.effort,
                   "--setting-sources", "", "--strict-mcp-config", "--mcp-config", str(work / "mcp.json"),
                   "--tools", "", "--allowedTools", "mcp__review__*",
                   "--permission-mode", "dontAsk", "--output-format", "stream-json", "--verbose",
                   "--json-schema", json.dumps(getattr(args, "output_schema", SCHEMA)), "--disable-slash-commands"]
        prompt = (instruction + "\n\nTask: Review the artifact available through the evidence tool. "
                  "All source data is fictional. The provided tools are the only evidence and "
                  "calculation facilities. Return the requested verdict, numeric value (as a "
                  "string, or null when unknown), reason and checks actually performed. "
                  "Use the output schema. Do not guess missing inputs.")
        if getattr(args, "review_contract", None):
            prompt = instruction + "\n\nTask: " + args.review_contract
        try:
            environment = clean_environment(work)
            code, stdout, stderr = communicate(command, prompt, work, environment, args.timeout)
            record.update({"exit_code": code, "output_bytes": len(stdout.encode()),
                           "output_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                           "stderr_bytes": len(stderr.encode())})
            if code:
                record["failure"] = "nonzero_exit"
            else:
                events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
                record["event_types"] = dict(Counter(event.get("type", "unknown") for event in events))
                for event in events:
                    if event.get("type") == "system" and event.get("subtype") == "init":
                        record["tool_inventory"] = event.get("tools", [])
                        record["plugin_count"] = len(event.get("plugins", []))
                        record["plugin_names"] = [plugin.get("name", "unknown") if isinstance(plugin, dict)
                                                  else "unknown" for plugin in event.get("plugins", [])]
                answer, models, inventory = decode_stream(stdout, set(args.allow_host_plugin),
                                                         getattr(args, "validator", None))
                # Deterministic scoring excludes prose semantics. The optional
                # model-assisted explanation grader runs separately below.
                record.update(getattr(args, "scorer", score)(item, answer))
                record.update({"status": "completed", "observed_models": models,
                               "observed_verdict": answer.get("verdict"),
                               "tool_inventory": inventory,
                               "reason_bytes": len(answer.get("reason", "").encode())})
        except subprocess.TimeoutExpired:
            record["failure"] = "timeout"
        except ValueError as exc:
            allowed = {"missing_runtime_attestation", "unexpected_tool_inventory",
                       "unexpected_plugin", "model_error", "invalid_answer_shape"}
            record["failure"] = str(exc) if str(exc) in allowed else "invalid_output"
        except Exception:
            record["failure"] = "setup_or_output_error"
        calls = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        record["tools"] = dict(Counter(call["tool"] for call in calls if call["ok"]))
        record["tool_errors"] = sum(not call["ok"] for call in calls)
        if record["status"] == "completed" and not record["tools"].get("evidence"):
            record.update({"status": "process_failure", "failure": "evidence_not_read"})
    record["seconds"] = round(time.monotonic() - started, 3)
    if record["status"] == "completed" and getattr(args, "explanation_grader", None):
        record.update(args.explanation_grader(item, answer, stdout))
    return record


def summarize(rows: list[dict]) -> dict:
    summary = {}
    for arm in sorted({row["arm"] for row in rows}):
        selected = [row for row in rows if row["arm"] == arm]
        complete = [row for row in selected if row["status"] == "completed"]
        summary[arm] = {"completed": len(complete), "process_failures": len(selected)-len(complete),
                        "objective_passes": sum(row["objective_pass"] for row in complete),
                        "seconds": round(sum(row["seconds"] for row in selected), 1)}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--cases", help="Comma-separated public case IDs; defaults to all in split")
    parser.add_argument("--arms", default="default,audit,reviewer")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-host-plugin", action="append", default=[],
                        help="Explicitly record an unavoidable host plugin; same allowance in all arms")
    args = parser.parse_args()
    args.claude_binary = str(Path(shutil.which("claude") or "claude").resolve())
    arms = args.arms.split(",")
    prompts = instructions()
    if len(set(arms)) != len(arms) or any(arm not in prompts for arm in arms):
        parser.error("unknown or duplicate arm")
    selected = [item for item in cases() if item["split"] == args.split]
    if args.cases:
        requested = args.cases.split(",")
        if len(set(requested)) != len(requested) or set(requested) - {item["id"] for item in selected}:
            parser.error("unknown, duplicate or wrong-split case")
        selected = [item for item in selected if item["id"] in args.cases.split(",")]
    if not selected or args.repeats < 1:
        parser.error("empty cases or invalid repeats")
    receipt = {"created_at": datetime.now(timezone.utc).isoformat(), "model": args.model,
               "effort": args.effort, "timeout_seconds": args.timeout, "split": args.split,
               "cases": [item["id"] for item in selected], "arms": arms, "repeats": args.repeats,
               "prompt_hashes": {arm: hashlib.sha256(prompts[arm].encode()).hexdigest() for arm in arms},
               "case_hash": hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest(),
               "harness_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in (Path(__file__), ROOT / "scripts/review_eval_tools.py",
                                               ROOT / "scripts/review_eval_cases.py")},
               "cli_binary_name": Path(args.claude_binary).name,
               "allowed_host_plugins": args.allow_host_plugin,
               "measurement": "verdict_and_value_only; explanation correctness not measured",
               "isolation": "auth-only config; fresh cwd; no built-in tools; synthetic MCP only",
               "rows": []}
    if args.dry_run:
        print(json.dumps({"cases": len(selected), "arms": arms, "planned_calls": len(selected)*len(arms)*args.repeats}))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for repeat in range(args.repeats):
        args.current_repeat = repeat
        for index, item in enumerate(selected):
            order = arms if (index + repeat) % 2 == 0 else list(reversed(arms))
            for arm in order:
                row = run_one(item, arm, prompts[arm], args)
                receipt["rows"].append(row)
                receipt["summary"] = summarize(receipt["rows"])
                args.output.write_text(json.dumps(receipt, indent=2) + "\n")
                print(json.dumps(row), flush=True)
    print(json.dumps(receipt["summary"]), flush=True)
    return 0 if all(row["status"] == "completed" for row in receipt["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
