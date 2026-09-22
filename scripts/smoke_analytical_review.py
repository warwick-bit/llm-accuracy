#!/usr/bin/env python3
"""Opt-in native skill smoke with synthetic inputs and content-free receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from review_eval_cases import cases, score
from run_review_eval import PLUGIN, ROOT, SCHEMA, clean_environment, communicate, decode_answer


def make_observer(work: Path) -> Path:
    plugin = work / "observer"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "hooks").mkdir()
    (plugin / ".claude-plugin/plugin.json").write_text(json.dumps({
        "name": "review-observer", "version": "1.0.0", "description": "Synthetic smoke event counter"}))
    (plugin / "observe.py").write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "event=json.load(sys.stdin).get('hook_event_name')\n"
        "if event in ('SubagentStart','SubagentStop'):\n"
        "    with (Path(__file__).parent/'events.txt').open('a') as f: f.write(event+'\\n')\n")
    hook = {"type": "command", "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/observe.py"'}
    (plugin / "hooks/hooks.json").write_text(json.dumps({"hooks": {
        name: [{"hooks": [hook]}] for name in ("SubagentStart", "SubagentStop")}}))
    return plugin


def control_passed(receipt: dict, without_skill: bool) -> bool:
    if not without_skill:
        return receipt.get("passed", False)
    return (receipt.get("status") == "completed"
            and receipt.get("target_skill_invoked", False)
            and receipt.get("target_skill_succeeded") is False
            and not receipt.get("passed", False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--without-skill", action="store_true", help="Negative control: omit target skill")
    args = parser.parse_args()
    item = next(item for item in cases() if item["id"] == "join-total")
    receipt = {"status": "process_failure", "model": args.model, "native_skill": True,
               "case": item["id"], "raw_responses_persisted": False}
    with tempfile.TemporaryDirectory(prefix="review-native-") as directory:
        work = Path(directory)
        fixture = work / "fixture.json"
        fixture.write_text(json.dumps(item["fixture"]))
        shutil.copyfile(ROOT / "scripts/review_eval_tools.py", work / "tools.py")
        candidate = work / "candidate"
        shutil.copytree(PLUGIN, candidate, ignore=shutil.ignore_patterns("__pycache__"))
        if args.without_skill:
            shutil.rmtree(candidate / "skills/analytical-review")
        observer = make_observer(work)
        trace = work / "tools.jsonl"
        mcp = work / "mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"review": {"command": sys.executable,
            "args": [str(work / "tools.py"), str(fixture), str(trace)]}}}))
        command = [str(Path(shutil.which("claude") or "claude").resolve()), "--print",
                   "--no-session-persistence", "--model", args.model, "--effort", "high",
                   "--setting-sources", "", "--strict-mcp-config", "--mcp-config", str(mcp),
                   "--plugin-dir", str(candidate), "--plugin-dir", str(observer),
                   "--tools", "Agent,Skill", "--allowedTools", "Agent,Skill,mcp__review__*",
                   "--permission-mode", "dontAsk", "--output-format", "stream-json", "--verbose",
                   "--json-schema", json.dumps(SCHEMA)]
        prompt = ("Invoke the Skill tool with skill llm-accuracy:analytical-review to "
                  "review the complete synthetic artifact "
                  "available from mcp__review__evidence. Use the available read-only query "
                  "and calculator as needed. Return verdict, requested numeric value as a "
                  "string or null if unknown, reason and checks performed. "
                  "After the skill returns, format its review using the output schema.")
        try:
            code, stdout, stderr = communicate(command, prompt, work, clean_environment(work), 120)
            receipt.update({"exit_code": code, "stderr_bytes": len(stderr.encode()),
                            "output_sha256": hashlib.sha256(stdout.encode()).hexdigest()})
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            blocks = [block for event in events
                      for block in event.get("message", {}).get("content", []) if isinstance(block, dict)]
            invocations = {block.get("id") for block in blocks
                           if block.get("type") == "tool_use" and block.get("name") == "Skill"
                           and block.get("input", {}).get("skill") == "llm-accuracy:analytical-review"}
            receipt["target_skill_invoked"] = bool(invocations)
            receipt["target_skill_succeeded"] = any(
                block.get("type") == "tool_result" and block.get("tool_use_id") in invocations
                and not block.get("is_error", False) for block in blocks)
            receipt["event_types"] = dict(Counter(event.get("type", "unknown") for event in events))
            for event in events:
                if event.get("type") == "system" and event.get("subtype") == "init":
                    receipt["plugins"] = [plugin.get("name") for plugin in event.get("plugins", [])]
                    receipt["tool_inventory"] = event.get("tools", [])
            final = [event for event in events if event.get("type") == "result"]
            if code == 0 and len(final) == 1:
                answer, models = decode_answer(json.dumps(final[0]))
                receipt.update(score(item, answer))
                receipt["observed_models"] = models
                receipt["status"] = "completed"
        except Exception:
            receipt["failure"] = "runtime_or_output_error"
        event_file = observer / "events.txt"
        receipt["subagent_events"] = dict(Counter(event_file.read_text().splitlines())) if event_file.exists() else {}
        calls = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        receipt["tools"] = dict(Counter(call["tool"] for call in calls if call["ok"]))
        receipt["passed"] = (receipt["status"] == "completed" and receipt.get("objective_pass", False)
                             and receipt.get("target_skill_invoked", False)
                             and receipt.get("target_skill_succeeded", False)
                             and receipt["subagent_events"].get("SubagentStart", 0) > 0
                             and receipt["subagent_events"].get("SubagentStop", 0) > 0
                             and receipt["tools"].get("evidence", 0) > 0)
    receipt["negative_control"] = args.without_skill
    receipt["child_lifecycle_causal_binding"] = "not_verified"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    return 0 if control_passed(receipt, args.without_skill) else 1


if __name__ == "__main__":
    raise SystemExit(main())
