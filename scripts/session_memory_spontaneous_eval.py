#!/usr/bin/env python3
"""Test skill selection on a synthetic old-evidence question, without a command cue.

The disposable skill points at this branch's CLI and synthetic index. Only
numeric/boolean receipts leave this process; model replies stay in memory.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from session_memory_model_eval import AGENT_SYSTEM, MODEL, make_fixture, score

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/evidence-memory/skills/memory/SKILL.md"
CLI = ROOT / "plugins/evidence-memory/hooks/memory.py"
SYSTEM = AGENT_SYSTEM.replace("Use only the supplied read-only Bash access.",
                              "Use available read-only tools when needed.")
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["integer", "null"]},
        "currency": {"type": ["string", "null"]},
        "basis": {"type": ["string", "null"]},
        "status": {"type": "string", "enum": ["found", "unavailable"]},
    },
    "required": ["value", "currency", "basis", "status"],
    "additionalProperties": False,
}


def write_plugin(path: Path, data: Path) -> None:
    manifest = path / ".claude-plugin/plugin.json"
    skill = path / "skills/memory/SKILL.md"
    manifest.parent.mkdir(parents=True)
    skill.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "eval-session-memory", "version": "0.0.1",
                                    "description": "Disposable current-session evidence memory eval"}),
                        encoding="utf-8")
    content = SKILL.read_text(encoding="utf-8")
    content = content.replace("${CLAUDE_PLUGIN_ROOT}/hooks/memory.py", str(CLI))
    content = content.replace("${CLAUDE_PLUGIN_DATA}", str(data))
    content = content.replace("${CLAUDE_SESSION_ID}", "synthetic-model-eval")
    skill.write_text(content, encoding="utf-8")


def restored_memory_packet(root: Path) -> str:
    """Use the production hook's bounded post-compaction cue, not a test prompt."""
    def load(name: str) -> Any:
        path = ROOT / "plugins/evidence-memory/hooks" / (name + ".py")
        spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    runtime = load("memory_runtime")
    bridge = load("memory")
    with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": str(root)}):
        packet = bridge.hook(runtime, {"session_id": "synthetic-model-eval", "cwd": str(root)},
                             restore=True)
    if not packet:
        raise AssertionError("memory restore packet unavailable")
    return packet


def one(mode: str, metric: str, *, structured_output: bool = False) -> dict[str, Any]:
    with (tempfile.TemporaryDirectory(prefix="session-memory-choice-data-", ignore_cleanup_errors=True) as data,
          tempfile.TemporaryDirectory(prefix="session-memory-choice-plugin-", ignore_cleanup_errors=True) as plugin_root):
        root = Path(data)
        context, store, oracle = make_fixture(root)
        database = store.path
        store.close()
        (root / "session.jsonl").unlink()
        if mode in ("restore_packet", "current_control"):
            context += "\n" + restored_memory_packet(root)
        plugin = Path(plugin_root) / "eval-memory"
        write_plugin(plugin, root)
        question = ("Which numbered unrelated phase did the latest compact summary say was completed?"
                    if mode == "current_control" else
                    f"What is the exact collected AUD value and current basis for {metric}?")
        hint = "Use the installed session memory skill if needed.\n" if mode == "skill_cue" else ""
        prompt = ("This session resumed after three compactions.\n"
                  f"Rolling ledger:\n{context}\n{hint}Question: {question}\n"
                  + ("Return only the digit." if mode == "current_control" else "Return only JSON."))
        system = ("Answer from the visible context. Use read-only tools only if needed. "
                  "Return exactly one digit with no other text." if mode == "current_control" else SYSTEM)
        command = ["claude", "-p", "--no-session-persistence", "--setting-sources", "",
                   "--strict-mcp-config", "--no-chrome", "--permission-prompts", "none",
                   "--tools", "Bash,Skill", "--allowedTools", "Bash,Skill",
                   "--plugin-dir", str(plugin), "--model", MODEL, "--effort", "low",
                   "--max-turns", "8", "--max-budget-usd", "0.30",
                   "--output-format", "json"]
        if structured_output:
            command.extend(("--json-schema", json.dumps(ANSWER_SCHEMA)))
        command.extend(("--system-prompt", system, prompt))
        raw = ""
        try:
            run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return {"mode": mode, "case": metric, "execution": "timeout", "scorable": False}
        connection = sqlite3.connect(database)
        try:
            counts = dict(connection.execute("SELECT outcome,count FROM retrieval_counts"))
        finally:
            connection.close()
        receipt: dict[str, Any] = {"mode": mode, "case": metric, "execution": "exited",
                                   "exit_code": run.returncode, "retrieval_counts": counts,
                                   "skill_retrieval_used": bool(counts), "scorable": False,
                                   "structured_output_requested": structured_output}
        if run.returncode:
            return receipt
        try:
            envelope = json.loads(run.stdout)
            receipt["terminal_reason"] = envelope.get("terminal_reason")
            receipt["model_turns"] = envelope.get("num_turns")
            usage = envelope["usage"]
            receipt["counted_tokens"] = sum(usage.get(key, 0) for key in
                                            ("input_tokens", "cache_creation_input_tokens",
                                             "cache_read_input_tokens", "output_tokens"))
            if envelope.get("terminal_reason") != "completed" or envelope.get("is_error"):
                return receipt
            raw = str(envelope.get("result") or "").strip()
            if mode == "current_control":
                receipt["scorable"] = True
                receipt["exact_answer"] = raw == "2"
                return receipt
            if structured_output:
                answer = envelope.get("structured_output")
                receipt["structured_output_present"] = isinstance(answer, dict)
                if not isinstance(answer, dict):
                    return receipt
            else:
                if raw.startswith("```"):
                    import re
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
                answer = json.loads(raw)
            receipt["scorable"] = True
            receipt["exact_answer"] = score(answer, oracle[metric])["correct"]
        except (KeyError, TypeError, ValueError):
            receipt["output_parse_failed"] = True
            if raw:
                receipt["output_shape"] = {
                    "characters": len(raw), "starts_with_object": raw.lstrip().startswith("{"),
                    "mentions_unavailable": '"unavailable"' in raw,
                    "mentions_found": '"found"' in raw,
                }
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("uncued", "skill_cue", "restore_packet",
                                           "current_control"), required=True)
    parser.add_argument("--metric", default="metric003")
    parser.add_argument("--structured-output", action="store_true",
                        help="Request schema-constrained JSON to separate content from formatting")
    args = parser.parse_args()
    if args.metric not in ("metric003", "metric009", "metric017", "metric031",
                           "metric045", "metric048", "metric999"):
        parser.error("metric must be one of the seven synthetic cases")
    if args.structured_output and args.mode == "current_control":
        parser.error("structured output requires a metric-answer case")
    print(json.dumps(one(args.mode, args.metric, structured_output=args.structured_output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
