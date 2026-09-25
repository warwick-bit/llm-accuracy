#!/usr/bin/env python3
"""Optional model-in-loop pilot for long-session evidence recovery.

Only synthetic fixtures and numeric/boolean receipts are written. Model replies
are parsed in memory and never saved. This measures assisted synthesis, not
whether an agent independently decides to invoke the memory skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from session_memory_replay import load, write

MODEL = "sonnet"
CASES = ("metric003", "metric009", "metric017", "metric031", "metric045")
AGENT_CASES = CASES + ("metric048", "metric999")
SYSTEM = (
    "Answer only from the supplied historical evidence. Return exactly one JSON "
    'object with keys value, currency, basis, status. basis must be exactly '
    '"collected_before_fees" when supported. status is "found" only if '
    'the exact metric value and current correction are supported; otherwise use '
    '"unavailable", with null other fields. For missing, failed, ambiguous or '
    'incomplete evidence, output exactly '
    '{"value":null,"currency":null,"basis":null,"status":"unavailable"}. '
    'Never add an explanation outside the JSON object. No tools.'
)
AGENT_SYSTEM = SYSTEM.removesuffix(" No tools.") + " Use only the supplied read-only Bash access."
MEMORY_CLI = Path(__file__).resolve().parents[1] / "plugins/evidence-memory/hooks/memory.py"


def value_for(index: int) -> int:
    return 100000 + int(hashlib.sha256(f"value/{index}".encode()).hexdigest()[:5], 16) % 800000


def tool_row(block: dict[str, Any], role: str = "assistant") -> dict[str, Any]:
    return {"sessionId": "synthetic-model-eval", "timestamp": "2026-09-01T00:00:00Z",
            "message": {"role": role, "content": [block]}}


def make_fixture(root: Path) -> tuple[str, Any, dict[str, dict[str, Any]]]:
    ledger, engine, runtime = load("session-ledger"), load("session_memory"), load("memory_runtime")
    transcript = root / "session.jsonl"
    session_id = "synthetic-model-eval"
    payload = {"session_id": session_id, "cwd": str(root), "transcript_path": str(transcript)}
    oracle = {}
    with transcript.open("wb") as stream:
        for index in range(48):
            metric = f"metric{index:03d}"
            call_id = f"call-{index:03d}"
            value = value_for(index)
            result = {"metric": metric, "gross": value + 117,
                      "collected_before_fees": value, "currency": "AUD"}
            write(stream, tool_row({"type": "tool_use", "id": call_id,
                                    "name": "query_dataset", "input": {"metric": metric}}))
            write(stream, tool_row({"type": "tool_result", "tool_use_id": call_id,
                                    "content": result}, "user"))
            if metric in CASES:
                oracle[metric] = {"value": value, "currency": "AUD",
                                  "basis": "collected_before_fees", "status": "found"}
        for metric in CASES:
            write(stream, {"message": {"role": "user", "content":
                  f"Correction for {metric}: use collected_before_fees, not gross."}})
        write(stream, tool_row({"type": "tool_use", "id": "call-048",
                                "name": "query_dataset", "input": {"metric": "metric048"}}))
        write(stream, tool_row({"type": "tool_result", "tool_use_id": "call-048",
                                "content": {"metric": "metric048", "error": "query failed"},
                                "is_error": True}, "user"))
        for metric in ("metric048", "metric999"):
            oracle[metric] = {"value": None, "currency": None, "basis": None,
                              "status": "unavailable"}
    ledger.update_ledger(payload, data_root=root)
    if not runtime.initialize_session(payload, data_root=root):
        raise AssertionError("memory session initialization failed")
    identity = runtime.session_identity(payload, root, runtime.utc_now())
    if not identity:
        raise AssertionError("fixture session scope missing")
    memory_path = runtime.session_directory(root, session_id) / "memory.sqlite3"
    runtime.secure_parent(memory_path)
    store = engine.Store(memory_path, session_id, identity[2], create=True)
    for metric in CASES:
        hits = [item for item in store.search(metric)["matches"] if item["kind"] == "result"]
        if hits:
            raise AssertionError("fixture indexed before sync")
    while store.sync(transcript)["status"] == "more_pending":
        pass
    for metric in CASES:
        hits = [item for item in store.search(metric)["matches"] if item["kind"] == "result"]
        if len(hits) != 1:
            raise AssertionError(f"expected one indexed result for {metric}")
        store.remember(metric, "correction", "Use collected_before_fees, not gross.",
                       [hits[0]["id"]])
    for phase in range(3):
        with transcript.open("ab") as stream:
            for index in range(90):
                filler = " ".join(hashlib.sha256(f"{phase}/{index}/{part}".encode()).hexdigest()
                                  for part in range(55))
                write(stream, {"message": {"role": "assistant", "content":
                      f"Unrelated work phase {phase} row {index}: {filler}"}})
        ledger.update_ledger(payload, data_root=root)
        ledger.write_compact_summary({**payload, "compact_summary":
                                      f"Completed unrelated phase {phase}."}, data_root=root)
        while store.sync(transcript)["status"] == "more_pending":
            pass
    context = ledger.session_start_context({**payload, "source": "compact"}, data_root=root)
    if not context:
        raise AssertionError("rolling ledger restore missing")
    if any(str(item["value"]) in context for item in oracle.values() if item["value"] is not None):
        raise AssertionError("fixture did not evict early exact values")
    return context, store, oracle


def evidence_packet(store: Any, question: str, *, placebo: bool = False) -> str:
    """Fixed query rule: only the metric identifier in the question is used."""
    match = re.search(r"\bmetric\d{3}\b", question)
    if not match:
        raise ValueError("question_missing_metric")
    metric = "metric047" if placebo else match.group()
    hits = [item for item in store.search(metric)["matches"] if item["kind"] == "result"]
    if len(hits) != 1:
        raise AssertionError("missing unique result")
    result = store.fetch(hits[0]["id"])
    if result["pairing"] != "paired" or result["host_error"] or result["next"] is not None:
        raise AssertionError("incomplete fixture result")
    packet = {"historical_result": json.loads(result["text"]), "pairing": result["pairing"]}
    if not placebo:
        state = store.state(limit=20)
        packet["current_correction"] = next(item["text"] for item in state["items"]
                                             if item["key"] == metric)
    else:
        packet["current_correction"] = "Unrelated synthetic note about another metric."
    return json.dumps(packet, ensure_ascii=False, sort_keys=True)


def scan_packet(transcript: Path, question: str) -> tuple[str, int]:
    """Control: one batched source scan, same evidence shape as indexed lookup."""
    match = re.search(r"\bmetric\d{3}\b", question)
    if not match:
        raise ValueError("question_missing_metric")
    metric = match.group()
    raw = transcript.read_bytes()
    result = None
    correction = None
    for line in raw.splitlines():
        row = json.loads(line)
        message = row.get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result" and block.get("content", {}).get("metric") == metric:
                    result = block
        elif isinstance(content, str) and content.startswith(f"Correction for {metric}:"):
            correction = content.split(": ", 1)[1].capitalize()
    if result is None or correction is None:
        raise AssertionError("scan control did not find exact evidence")
    return json.dumps({"historical_result": result, "pairing": "paired",
                       "current_correction": correction}, ensure_ascii=False, sort_keys=True), len(raw)


def score(reply: Any, expected: dict[str, Any]) -> dict[str, Any]:
    """Strict scorer; the negative control must fail before model runs."""
    if not isinstance(reply, dict):
        return {"correct": False, "wrong_fields": ["unparseable"], "abstained": False}
    keys = tuple(expected)
    wrong = [key for key in keys if reply.get(key) != expected[key]]
    wrong.extend(key for key in reply if key not in expected)
    return {"correct": not wrong, "wrong_fields": wrong,
            "abstained": reply.get("status") == "unavailable"}


def invoke(prompt: str, *, agentic: bool = False, cwd: Path | None = None) -> tuple[Any, dict[str, Any]]:
    command = ["claude", "--safe-mode", "--strict-mcp-config", "-p", "--tools",
               "Bash" if agentic else ""]
    if agentic:
        command.extend(("--allowedTools", "Bash"))
    command.extend(("--model", MODEL, "--effort", "low",
               "--max-turns", "8" if agentic else "1", "--output-format", "json",
               "--system-prompt", AGENT_SYSTEM if agentic else SYSTEM))
    command.append(prompt)
    run = subprocess.run(command, capture_output=True, text=True, timeout=120,
                         check=False, cwd=cwd)
    if run.returncode:
        return None, {"status": "process_error"}
    try:
        envelope = json.loads(run.stdout)
        if envelope.get("terminal_reason") != "completed" or envelope.get("is_error"):
            return None, {"status": "incomplete"}
        raw = envelope["result"].strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        usage = envelope["usage"]
        inputs = sum(usage.get(key, 0) for key in
                     ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        outputs = usage.get("output_tokens", 0)
        try:
            answer = json.loads(raw)
            answer_parsed = isinstance(answer, dict)
        except ValueError:
            answer, answer_parsed = None, False
        return answer, {"status": "complete", "input_tokens": inputs,
                        "output_tokens": outputs, "total_tokens": inputs + outputs,
                        "cost_usd": envelope.get("total_cost_usd"),
                        "model_turns": envelope.get("num_turns"),
                        "permission_denials": len(envelope.get("permission_denials", [])),
                        "answer_parsed": answer_parsed}
    except (KeyError, TypeError, ValueError):
        return None, {"status": "unparseable"}


def run_eval(case_count: int) -> dict[str, Any]:
    if score({"value": 0, "currency": "AUD", "basis": "gross", "status": "found"},
             {"value": 1, "currency": "AUD", "basis": "collected_before_fees", "status": "found"})["correct"]:
        raise AssertionError("negative control passed")
    with tempfile.TemporaryDirectory(prefix="session-memory-model-eval-") as directory:
        root = Path(directory)
        context, store, oracle = make_fixture(root)
        receipts = []
        for index, metric in enumerate(CASES[:case_count]):
            question = f"What is the exact collected AUD value and current basis for {metric}?"
            scan, scan_bytes = scan_packet(root / "session.jsonl", question)
            packets = {"ledger": "", "placebo": evidence_packet(store, question, placebo=True),
                       "memory": evidence_packet(store, question), "scan": scan}
            order = ("ledger", "placebo", "memory", "scan")
            for arm in (order if index % 2 == 0 else tuple(reversed(order))):
                prompt = ("This is a resumed session after three compactions.\n"
                          f"Rolling ledger:\n{context}\n"
                          f"Additional historical evidence:\n{packets[arm]}\n"
                          f"Question: {question}\nReturn only JSON.")
                answer, measured = invoke(prompt)
                receipt = {"case": metric, "arm": arm, "packet_characters": len(packets[arm]),
                           "transcript_bytes_read": scan_bytes if arm == "scan" else 0,
                           **measured}
                if measured["status"] == "complete":
                    receipt.update(score(answer, oracle[metric]))
                receipts.append(receipt)
        store.close()
    return {"population": "synthetic long-session questions; assisted packet retrieval",
            "model": MODEL, "effort": "low", "compactions": 3, "cases": case_count,
            "negative_control": "failed_as_expected", "receipts": receipts,
            "limits": "No agentic retrieval choice, real-session frequency, or live-user accuracy measured."}


def run_agentic(case_count: int, start_index: int = 0, *, delete_source: bool = False) -> dict[str, Any]:
    receipts = []
    for index, metric in enumerate(AGENT_CASES[start_index:case_count], start=start_index):
        question = f"What is the exact collected AUD value and current basis for {metric}?"
        order = ("scan", "memory") if index % 2 == 0 else ("memory", "scan")
        for arm in order:
            # Each worker sees only its own source. The scan arm cannot find
            # the index, and the memory arm cannot fall back to the transcript.
            with tempfile.TemporaryDirectory(prefix="session-memory-agentic-eval-") as directory:
                root = Path(directory)
                context, store, oracle = make_fixture(root)
                database = store.path
                store.close()
                if arm == "scan":
                    database.unlink()
                    if delete_source:
                        (root / "session.jsonl").unlink()
                else:
                    (root / "session.jsonl").unlink()
                access = (
                    f"The transcript is session.jsonl in the working directory. Use rg -n {metric} "
                    "session.jsonl to locate old results and corrections; inspect matching JSON."
                    if arm == "scan" else
                    f"The current-session memory CLI is {MEMORY_CLI}. Run "
                    f"python3 {MEMORY_CLI} --plugin-data {root} --session-id synthetic-model-eval "
                    f"lookup {metric}. Check status, logged call, historical result and "
                    "current correction in its response; use search/fetch only if lookup is incomplete."
                )
                prompt = ("This session resumed after three compactions. Use the available "
                          "read-only Bash tool to retrieve evidence needed for the question.\n"
                          f"Rolling ledger:\n{context}\n{access}\n"
                          f"Question: {question}\nReturn only JSON.")
                answer, measured = invoke(prompt, agentic=True, cwd=root)
                receipt = {"case": metric, "arm": arm, **measured}
                if measured["status"] == "complete":
                    receipt.update(score(answer, oracle[metric]))
                receipts.append(receipt)
    return {"population": "synthetic agentic retrieval after three simulated compactions",
            "model": MODEL, "effort": "low", "compactions": 3,
            "case_range": [start_index, case_count], "cases": case_count - start_index,
            "scan_source_deleted": delete_source, "memory_source_deleted": True,
            "receipts": receipts,
            "limits": "Prompt names the retrieval tool; this does not test spontaneous skill selection or real sessions."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, choices=range(1, len(AGENT_CASES) + 1), default=1)
    parser.add_argument("--agentic", action="store_true")
    parser.add_argument("--delete-source", action="store_true",
                        help="Agentic source-loss stratum after the index is built")
    parser.add_argument("--start-index", type=int, default=0,
                        help="Agentic case index to resume from; receipts retain the range")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.agentic and args.cases > len(CASES):
        parser.error("packet comparison has five positive cases")
    if args.start_index < 0 or args.start_index >= args.cases or (args.start_index and not args.agentic):
        parser.error("start-index must select an agentic case before cases")
    if args.delete_source and not args.agentic:
        parser.error("delete-source requires agentic mode")
    result = (run_agentic(args.cases, args.start_index, delete_source=args.delete_source)
              if args.agentic else run_eval(args.cases))
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if all(item["status"] == "complete" for item in result["receipts"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
