#!/usr/bin/env python3
"""Opt-in free-form review comparison. Never persist model prose or tool payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from review_everyday_extract import (
    SCHEMA, calibration_cases, encode_payload, equal_value, normalize, score_extraction, validate_extraction,
)
from run_review_eval import PLUGIN, ROOT, body, clean_environment, communicate


TASK = "Review the work available from the evidence tool for correctness and material issues."
TOOLS = {"mcp__review__evidence", "mcp__review__query", "mcp__review__calculate"}


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def prompts():
    guidance = "\n\n".join(body(PLUGIN / p) for p in (
        "skills/claim-fidelity/SKILL.md", "skills/verify-technical/SKILL.md",
        "references/evidence-discipline.md"))
    reviewer = body(PLUGIN / "skills/analytical-review/SKILL.md").replace("$ARGUMENTS", "the supplied work")
    filler = "Review the work carefully and explain your assessment clearly. "
    placebo = " ".join((filler * (len(reviewer.split()) + 1)).split()[:len(reviewer.split())])
    return {"default": TASK, "plugin": guidance + "\n\n" + TASK,
            "reviewer": guidance + "\n\n" + reviewer + "\n\n" + TASK,
            "placebo": guidance + "\n\n" + placebo + "\n\n" + TASK}


def provenance(args):
    files = [Path(__file__), ROOT / "scripts/review_everyday_extract.py",
             ROOT / "scripts/review_everyday_cases.py", ROOT / "scripts/run_review_eval.py",
             ROOT / "scripts/review_eval_tools.py"]
    plugin_files = sorted(p for p in PLUGIN.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return {"model": args.model, "extractor_model": args.extractor_model, "effort": args.effort,
            "binary_sha256": digest(Path(args.claude_binary).read_bytes()),
            "host_plugins": sorted(args.host_plugins),
            "plugin_version": json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())["version"],
            "source_hashes": {p.name: digest(p.read_bytes()) for p in files},
            "plugin_sha256": digest({str(p.relative_to(PLUGIN)): digest(p.read_bytes()) for p in plugin_files}),
            "prompt_hashes": {arm: digest(prompt) for arm, prompt in prompts().items()}}


def command(args, structured=False):
    cmd = [args.claude_binary, "--print", "--no-session-persistence", "--model",
           args.extractor_model if structured else args.model, "--effort", args.effort,
           "--setting-sources", "", "--strict-mcp-config", "--tools", "",
           "--permission-mode", "dontAsk", "--output-format", "stream-json", "--verbose",
           "--include-hook-events", "--disable-slash-commands"]
    if structured:
        cmd += ["--json-schema", json.dumps(SCHEMA)]
    return cmd


def parse(output, code, args, *, structured=False, plugin=False):
    events = [json.loads(line) for line in output.splitlines() if line.strip()]
    init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    finals = [e for e in events if e.get("type") == "result"]
    if code or len(init) != 1 or len(finals) != 1 or finals[0].get("is_error"):
        raise ValueError("runtime_failure")
    names = sorted(p.get("name", "unknown") for p in init[0].get("plugins", []))
    expected = sorted(args.host_plugins + (["llm-accuracy"] if plugin else []))
    if names != expected:
        raise ValueError("plugin_inventory_drift")
    allowed_tools = {"StructuredOutput"} if structured else TOOLS
    if set(init[0].get("tools", [])) != allowed_tools:
        raise ValueError("tool_inventory_drift")
    model = args.extractor_model if structured else args.model
    if init[0].get("model") != model or set(finals[0].get("modelUsage", {})) != {model}:
        raise ValueError("model_drift")
    hooks = [e for e in events if e.get("type") == "system" and e.get("subtype") == "hook_response"]
    fidelity = sum("CLAIM FIDELITY CHECK" in str(e.get("stdout", "")) for e in hooks)
    if (plugin and fidelity != 1) or (not plugin and hooks):
        raise ValueError("hook_activation_failure")
    result = finals[0].get("structured_output") if structured else finals[0].get("result")
    if structured and result is None:
        result = json.loads(finals[0].get("result", ""))
    if not structured and (not isinstance(result, str) or not result.strip()):
        raise ValueError("empty_review")
    return result, {"models": [model], "plugins": names,
                    "tools": sorted(allowed_tools), "fidelity_hook_responses": fidelity,
                    "hook_responses": len(hooks)}


def call(args, work, cmd, prompt, *, structured=False, plugin=False):
    started = time.monotonic()
    record = {"status": "process_failure"}
    try:
        code, output, error = communicate(cmd, prompt, work, clean_environment(work), args.timeout)
        record.update({"exit_code": code, "output_sha256": digest(output.encode()),
                       "output_bytes": len(output.encode()), "stderr_bytes": len(error.encode())})
        # Retain only sanitized inventory diagnostics if strict validation rejects.
        for line in output.splitlines():
            event = json.loads(line)
            if event.get("type") == "system" and event.get("subtype") == "init":
                record["observed_plugin_count"] = len(event.get("plugins", []))
                known = {"telemetry", "agents-md", "llm-accuracy"}
                record["observed_plugins"] = [p.get("name") if p.get("name") in known else "unknown"
                                              for p in event.get("plugins", [])]
        result, metadata = parse(output, code, args, structured=structured, plugin=plugin)
        record.update(status="completed", **metadata)
        return result, record
    except subprocess.TimeoutExpired:
        record["failure"] = "timeout"
    except ValueError as exc:
        allowed = {"runtime_failure", "plugin_inventory_drift", "tool_inventory_drift",
                   "model_drift", "hook_activation_failure", "empty_review"}
        record["failure"] = str(exc) if str(exc) in allowed else "invalid_output"
    except Exception:
        record["failure"] = "setup_or_runtime_failure"
    finally:
        record["seconds"] = round(time.monotonic()-started, 3)
    return None, record


def extract(item, review, args):
    with tempfile.TemporaryDirectory(prefix="review-extract-", ignore_cleanup_errors=True) as directory:
        answer, record = call(args, Path(directory), command(args, True), encode_payload(item, review), structured=True)
    if record["status"] == "completed":
        try:
            validate_extraction(answer, item, review)
        except (ValueError, TypeError):
            record.update(status="process_failure", failure="extraction_validation")
            answer = None
    return answer, record


def review(item, arm, args):
    with tempfile.TemporaryDirectory(prefix="review-everyday-", ignore_cleanup_errors=True) as directory:
        work = Path(directory)
        (work / "fixture.json").write_text(json.dumps(item["fixture"]))
        shutil.copyfile(ROOT / "scripts/review_eval_tools.py", work / "tools.py")
        trace = work / "trace.jsonl"
        mcp = {"mcpServers": {"review": {"command": sys.executable,
               "args": [str(work / "tools.py"), str(work / "fixture.json"), str(trace)]}}}
        (work / "mcp.json").write_text(json.dumps(mcp))
        cmd = command(args) + ["--mcp-config", str(work / "mcp.json"), "--allowedTools", "mcp__review__*"]
        if arm != "default":
            shutil.copytree(PLUGIN, work / "plugin", ignore=shutil.ignore_patterns("__pycache__"))
            cmd += ["--plugin-dir", str(work / "plugin")]
        answer, record = call(args, work, cmd, prompts()[arm], plugin=arm != "default")
        calls = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        record["tool_calls"] = dict(Counter(c["tool"] for c in calls if c["ok"]))
        record["tool_errors"] = sum(not c["ok"] for c in calls)
        if record["status"] == "completed" and not record["tool_calls"].get("evidence"):
            record.update(status="process_failure", failure="evidence_not_read")
    row = {"case": item["id"], "domain": item["domain"], "arm": arm, "review": record}
    if record["status"] == "completed":
        extracted, row["extraction"] = extract(item, answer, args)
        if extracted is not None:
            row["score"] = score_extraction(extracted, item)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--extractor-model", required=True)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--host-plugins", nargs="*", default=["agents-md", "telemetry"])
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--cases")
    parser.add_argument("--arms", default="default,plugin,reviewer")
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.claude_binary = str(Path(shutil.which("claude") or "claude").resolve())
    config = provenance(args)
    receipt = {"config": config, "mode": "calibration" if args.calibrate else "comparison",
               "round": args.round, "rows": [], "complete": False}
    if args.calibrate:
        for control in calibration_cases():
            answer, run = extract(control, control["review"], args)
            expected = control.get("expected_rows", {"x": (control.get("expected_status"), control.get("expected_value"))})
            matched = answer is not None and all(
                row["status"] == expected[row["id"]][0] and equal_value(
                    normalize(row, next(g for g in control["gold"] if g["id"] == row["id"])), expected[row["id"]][1])
                for row in answer["claims"])
            observed = [] if answer is None else [
                {"id": row["id"], "status": row["status"],
                 "status_matches": row["status"] == expected[row["id"]][0],
                 "value_matches": equal_value(normalize(row, next(g for g in control["gold"] if g["id"] == row["id"])), expected[row["id"]][1])}
                for row in answer["claims"]]
            receipt["rows"].append({"control": control["id"], "run": run, "matched": matched, "observed": observed})
            args.output.write_text(json.dumps(receipt, indent=2)+"\n")
            print(json.dumps({"control": control["id"], "status": run["status"], "matched": matched}), flush=True)
            if not matched:
                return 1
    else:
        from review_everyday_cases import cases
        calibration = json.loads(args.calibration.read_text()) if args.calibration else {}
        if calibration.get("config") != config or not calibration.get("complete") or calibration.get("mode") != "calibration":
            parser.error("matching successful calibration required")
        controls = calibration_cases()
        if {r.get("control") for r in calibration.get("rows", [])} != {c["id"] for c in controls} or not all(
                r.get("matched") is True and r.get("run", {}).get("status") == "completed" for r in calibration["rows"]):
            parser.error("calibration controls incomplete")
        inventory = {item["id"]: item for item in cases()}
        selected = args.cases.split(",") if args.cases else list(inventory)
        arms = args.arms.split(",")
        if not set(selected) <= set(inventory) or len(selected) != len(set(selected)) or not set(arms) <= set(prompts()) or len(arms) != len(set(arms)):
            parser.error("unknown or duplicate case/arm")
        receipt["calibration_sha256"] = digest(args.calibration.read_bytes())
        for index, case in enumerate(selected):
            offset = (index+args.round) % len(arms)
            for arm in arms[offset:]+arms[:offset]:
                row = review(inventory[case], arm, args)
                receipt["rows"].append(row)
                args.output.write_text(json.dumps(receipt, indent=2)+"\n")
                print(json.dumps({"case": case, "arm": arm, "status": row["review"]["status"],
                                  "all_claims_match": row.get("score", {}).get("all_claims_match")}), flush=True)
                if "score" not in row:
                    return 1
    receipt["complete"] = True
    args.output.write_text(json.dumps(receipt, indent=2)+"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
