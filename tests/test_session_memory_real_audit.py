"""The local real-log audit publishes aggregate receipts only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/session_memory_real_audit.py"


def audit_module():
    spec = importlib.util.spec_from_file_location("session_memory_real_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(path, *, retained=False):
    marker = "metricA123456789"
    rows = [
        {"type": "session_meta", "payload": {"id": "synthetic-session"}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "call-1",
                                              "name": "query_dataset", "arguments": "{}"}},
        {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "call-1",
                                              "output": {"metric": marker, "value": 17}}},
        {"type": "compacted", "payload": {"replacement_history": "phase one"}},
        {"type": "compacted", "payload": {"replacement_history": "phase two"}},
        {"type": "compacted", "payload": {"replacement_history": marker if retained else "phase three"}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                              "content": [{"type": "output_text", "text": f"Checked {marker}."}]}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return marker


def test_real_audit_replays_exact_result_without_source_and_emits_no_content(tmp_path):
    marker = fixture(tmp_path / "session.jsonl")
    report = audit_module().audit(tmp_path, 2**20)
    assert report["long_sessions"] == 1
    assert report["candidate_sessions"] == 1
    assert report["replay"]["exact_result_after_source_copy_deleted"] is True
    assert report["replay"]["lookup_transcript_bytes"] == 0
    assert marker not in json.dumps(report)
    assert "synthetic-session" not in json.dumps(report)


def test_real_audit_excludes_evidence_already_in_compacted_context(tmp_path):
    fixture(tmp_path / "session.jsonl", retained=True)
    report = audit_module().audit(tmp_path, 2**20)
    assert report["long_sessions"] == 1
    assert report["candidate_sessions"] == 0
    assert report["replay"]["status"] == "no_eligible_case"


def test_claude_real_audit_replays_without_exposing_tool_result(tmp_path):
    marker = "metricB987654321"
    def row(role, block, **extra):
        return {"type": role, "sessionId": "synthetic-claude-session",
                "timestamp": "2026-09-01T00:00:00Z",
                "message": {"role": role, "content": [block]}, **extra}
    rows = [
        row("assistant", {"type": "tool_use", "id": "call-1", "name": "query_dataset", "input": {}}),
        row("user", {"type": "tool_result", "tool_use_id": "call-1", "content": marker}),
        *(row("user", {"type": "text", "text": f"phase {index}"}, isCompactSummary=True)
          for index in range(3)),
        row("assistant", {"type": "text", "text": f"Earlier result was {marker}."}),
    ]
    (tmp_path / "session.jsonl").write_text("".join(json.dumps(item) + "\n" for item in rows),
                                            encoding="utf-8")
    report = audit_module().audit(tmp_path, 2**20, host="claude")
    assert report["long_sessions"] == 1
    assert report["candidate_sessions"] == 1
    assert report["replay"]["exact_result_after_source_copy_deleted"] is True
    assert marker not in json.dumps(report)
