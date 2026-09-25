#!/usr/bin/env python3
"""Raw-free local audit of earlier tool evidence in long Codex or Claude sessions.

No transcript text, IDs, paths, search keys or model replies are emitted or
written. Lexical overlap is an opportunity signal, not proof of dependence.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

ENGINE_PATH = Path(__file__).resolve().parents[1] / "plugins/session-ledger/hooks/session_memory.py"
TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9][A-Za-z0-9_.:/-]{9,}(?![A-Za-z0-9])")


def engine() -> Any:
    spec = importlib.util.spec_from_file_location("audit_session_memory", ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tokens(value: str) -> set[str]:
    normalized = (word.rstrip("._:/-").lower() for word in TOKEN.findall(value))
    return {word for word in normalized if len(word) >= 10 and any(c.isdigit() for c in word)}


def message_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    return " ".join(part.get("text", "") for part in content
                    if isinstance(part, dict) and isinstance(part.get("text"), str))


def rows(path: Path):
    """Stream one log; a large data-work session need not fit in memory."""
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def is_compaction(row: dict[str, Any], host: str) -> bool:
    return row.get("isCompactSummary") is True if host == "claude" else row.get("type") == "compacted"


def prose(row: dict[str, Any], host: str) -> tuple[str, str]:
    """Return only ordinary user/assistant text, never tool result bodies."""
    if host == "codex":
        payload = row.get("payload")
        if row.get("type") != "response_item" or not isinstance(payload, dict) or payload.get("type") != "message":
            return "", ""
        return payload.get("role", ""), message_text(payload)
    message = row.get("message")
    if row.get("type") not in ("user", "assistant") or not isinstance(message, dict):
        return "", ""
    content = message.get("content")
    if isinstance(content, str):
        return row["type"], content
    if isinstance(content, list):
        text = " ".join(part.get("text", "") for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                        and isinstance(part.get("text"), str))
        return row["type"], text
    return "", ""


def inspect_path(path: Path, module: Any, host: str) -> dict[str, Any] | None:
    compactions = 0
    early_results: set[str] = set()
    earlier_user: set[str] = set()
    later_user: set[str] = set()
    later_assistant: set[str] = set()
    retained: set[str] = set()
    session_id = None
    for row in rows(path):
        if session_id is None:
            if host == "claude" and isinstance(row.get("sessionId"), str):
                session_id = row["sessionId"]
            elif host == "codex" and row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
                session_id = row["payload"].get("id")
        if is_compaction(row, host):
            compactions += 1
            if compactions == 3:
                retained = tokens(json.dumps(row if host == "claude" else row.get("payload"), ensure_ascii=False))
            continue
        role, text = prose(row, host)
        if compactions == 0:
            if role == "user":
                earlier_user.update(tokens(text))
            for event in module.tool_events(row):
                if event["kind"] == "result":
                    early_results.update(tokens(module.encoded(event["body"])))
        elif compactions >= 3:
            if role == "user":
                later_user.update(tokens(text))
            elif role == "assistant":
                later_assistant.update(tokens(text))
    if compactions < 3:
        return None
    candidates = (early_results - earlier_user - later_user - retained) & later_assistant
    return {"compactions": compactions, "session_id": session_id,
            "candidate_count": len(candidates), "candidates": candidates}


def matching_event(path: Path, module: Any, host: str, candidates: set[str]) -> dict[str, Any]:
    for row in rows(path):
        if is_compaction(row, host):
            break
        for event in module.tool_events(row):
            if event["kind"] == "result" and candidates & tokens(module.encoded(event["body"])):
                return event
    raise ValueError("candidate_result_unavailable")


def replay(path: Path, session_id: str, candidates: set[str], module: Any, host: str) -> dict[str, Any]:
    """Index a disposable copy, delete that copy, and compare paged exact JSON."""
    event = matching_event(path, module, host, candidates)
    with tempfile.TemporaryDirectory(prefix="session-memory-real-audit-") as directory:
        root = Path(directory)
        source = root / "source.jsonl"
        shutil.copyfile(path, source)
        store = module.Store(root / "memory.sqlite3", session_id, "audit", create=True)
        try:
            batches = 0
            while batches < 1000:
                result = store.sync(source)
                batches += 1
                if result["status"] != "more_pending":
                    break
            events = store.status()["events"]
            source.unlink()
            body = module.encoded(event["body"])
            identity = module.sha(module.encoded(["result", event["call_id"], body]).encode())
            pieces = []
            offset = 0
            while True:
                packet = store.fetch(identity, start=offset)
                pieces.append(packet["text"])
                if packet["next"] is None:
                    break
                offset = packet["next"]
            return {"sync_status": result["status"], "sync_batches": batches,
                    "indexed_events": events, "exact_result_after_source_copy_deleted":
                        "".join(pieces) == body,
                    "lookup_transcript_bytes": packet["transcript_bytes_read"]}
        finally:
            store.close()


def audit(root: Path, max_replay_bytes: int, *, host: str = "codex") -> dict[str, Any]:
    module = engine()
    files = 0
    long_sessions = 0
    candidate_sessions = 0
    candidate_tokens = 0
    eligible = []
    malformed = 0
    for path in root.rglob("*.jsonl"):
        files += 1
        try:
            result = inspect_path(path, module, host)
        except (OSError, ValueError, TypeError):
            malformed += 1
            continue
        if result is None:
            continue
        long_sessions += 1
        candidate_tokens += result["candidate_count"]
        if result["candidate_count"]:
            candidate_sessions += 1
            if (isinstance(result["session_id"], str) and result["candidates"]
                    and path.stat().st_size <= max_replay_bytes):
                eligible.append((path.stat().st_size, path, result))
    eligible.sort(key=lambda item: item[0])
    replay_receipt = {"status": "no_eligible_case"}
    if eligible:
        size, path, result = eligible[0]
        try:
            replay_receipt = {"status": "attempted", "source_mib": round(size / 2**20, 1),
                              **replay(path, result["session_id"], result["candidates"], module, host)}
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, ArithmeticError) as exc:
            replay_receipt = {"status": "failed", "error_class": type(exc).__name__}
    return {"population": ("local Claude JSONL files; three or more compact summary rows" if host == "claude"
                           else "local Codex JSONL files; three or more compacted rows"),
            "files_scanned": files, "malformed_files": malformed,
            "long_sessions": long_sessions, "candidate_sessions": candidate_sessions,
            "candidate_tokens": candidate_tokens,
            "candidate_definition": ">=10-character token containing a digit, in an earlier indexed tool result and later assistant message; absent from earlier/later user text and third compacted payload",
            "inference_limit": "Lexical overlap does not establish need, accuracy gain, or retrieval use; semantic paraphrases are missed",
            "replay": replay_receipt}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    parser.add_argument("--max-replay-mib", type=int, default=32)
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.max_replay_mib * 2**20, host=args.host), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
