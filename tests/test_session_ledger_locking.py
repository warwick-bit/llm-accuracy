"""Cross-process ledger serialization, including a lost-update negative control."""

import importlib.util
import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / "plugins/session-ledger/hooks/session-ledger.py"
)
WORKER = r"""
import importlib.util, sys
from pathlib import Path
from contextlib import nullcontext
spec = importlib.util.spec_from_file_location("ledger", sys.argv[1])
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)
root, label, unlocked = Path(sys.argv[2]), sys.argv[3], sys.argv[4] == "True"
if unlocked:
    ledger.session_lock = lambda *_: nullcontext()
original = ledger.load_current_record
def paused_read(*args, **kwargs):
    result = original(*args, **kwargs)
    print("read", flush=True)
    sys.stdin.readline()
    return result
ledger.load_current_record = paused_read
ok = ledger.update_ledger({"session_id": "synthetic-session", "cwd": str(root),
                          "prompt": label}, data_root=root)
sys.exit(0 if ok else 1)
"""


def load_ledger():
    spec = importlib.util.spec_from_file_location("ledger", HOOK)
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    return ledger


@pytest.mark.parametrize(
    "action", ["initialize_session", "update_ledger", "write_compact_summary"]
)
def test_navigation_preserves_history_and_continues_each_writer(tmp_path, action):
    ledger = load_ledger()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    original = {"session_id": "synthetic-session", "cwd": str(tmp_path / "first"),
                "prompt": "Synthetic first", "compact_summary": "Synthetic summary"}
    assert ledger.update_ledger(original, data_root=tmp_path, now=now)
    assert ledger.write_compact_summary(original, data_root=tmp_path, now=now)
    path = ledger.record_path(tmp_path, "synthetic-session")
    before = path.read_bytes()
    other = {**original, "cwd": str(tmp_path / "other"),
             "prompt": "Synthetic other", "compact_summary": "Other summary"}

    assert getattr(ledger, action)(other, data_root=tmp_path, now=now + timedelta(hours=1))
    assert json.loads(path.read_text())["workspace_hash"] == json.loads(before)["workspace_hash"]
    assert ledger.session_start_context(
        {**other, "source": "resume"}, data_root=tmp_path, now=now
    ) is not None

    assert ledger.update_ledger(
        {**original, "prompt": "Synthetic returned"}, data_root=tmp_path,
        now=now + timedelta(hours=2),
    )
    record = json.loads(path.read_text())
    assert record["created_at"] == json.loads(before)["created_at"]
    assert record["compact_summary"] == (
        "Other summary" if action == "write_compact_summary" else "Synthetic summary"
    )
    expected = ["Synthetic first"]
    if action == "update_ledger":
        expected.append("Synthetic other")
    assert [entry["text"] for entry in record["entries"]] == expected + ["Synthetic returned"]


def test_explicit_plan_boundary_allows_workspace_change(tmp_path):
    ledger = load_ledger()
    original = {"session_id": "synthetic-session", "cwd": str(tmp_path / "first"),
                "prompt": "Synthetic first"}
    assert ledger.update_ledger(original, data_root=tmp_path)
    other = {**original, "cwd": str(tmp_path / "other"), "prompt": "Synthetic other"}
    assert ledger.begin_plan("synthetic-session", data_root=tmp_path, cwd=other["cwd"])
    assert ledger.update_ledger(other, data_root=tmp_path)
    record = json.loads(ledger.record_path(tmp_path, "synthetic-session").read_text())
    assert [entry["text"] for entry in record["entries"]] == ["Synthetic other"]


@pytest.mark.parametrize(
    "action", ["initialize_session", "update_ledger", "write_compact_summary"]
)
def test_session_anchor_is_rechecked_after_acquiring_lock(tmp_path, monkeypatch, action):
    ledger = load_ledger()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path / "first"),
               "prompt": "Synthetic first", "compact_summary": "Synthetic summary"}
    owner = ledger.record_for(
        workspace_hash=ledger.canonical_workspace_hash(str(tmp_path / "other")),
        plan_id=ledger.DEFAULT_PLAN_ID, now=now,
    )
    original_lock = ledger.session_lock

    @contextmanager
    def lock_after_other_writer(root, session_id):
        with original_lock(root, session_id):
            ledger.write_json_atomic(ledger.record_path(root, session_id), owner)
            yield

    monkeypatch.setattr(ledger, "session_lock", lock_after_other_writer)
    assert getattr(ledger, action)(payload, data_root=tmp_path, now=now)
    record = json.loads(ledger.record_path(tmp_path, "synthetic-session").read_text())
    assert record["workspace_hash"] == owner["workspace_hash"]


def test_expired_workspace_record_does_not_prevent_new_capture(tmp_path):
    ledger = load_ledger()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path / "first"),
               "prompt": "Synthetic first"}
    assert ledger.update_ledger(payload, data_root=tmp_path, now=now)
    assert ledger.update_ledger(
        {**payload, "cwd": str(tmp_path / "other"), "prompt": "Synthetic other"},
        data_root=tmp_path, now=now + timedelta(days=31),
    )
    record = json.loads(ledger.record_path(tmp_path, "synthetic-session").read_text())
    assert [entry["text"] for entry in record["entries"]] == ["Synthetic other"]


def invoke_hook(ledger, monkeypatch, capsys, root, payload, action="capture"):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(root))
    monkeypatch.setattr(ledger.sys, "stdin", io.StringIO(json.dumps(payload)))
    assert ledger.main([action]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert ledger.HOOK_NOTICES.get() is None
    return json.loads(output.out) if output.out else {}


def test_navigation_does_not_emit_a_false_capture_failure(
    tmp_path, monkeypatch, capsys
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path / "first"),
               "prompt": "PRIVATE_FIXTURE_TEXT"}
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                         {**payload, "cwd": str(tmp_path / "other")})
    assert result == {}
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}


@pytest.mark.parametrize("failure", ["timeout", "unavailable", "storage", "unexpected"])
def test_failure_notices_are_specific_sanitized_and_nonblocking(
    tmp_path, monkeypatch, capsys, failure
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path), "prompt": "synthetic"}
    expected = failure
    if failure in {"timeout", "unavailable"}:
        monkeypatch.setattr(ledger, "fcntl", None)
        monkeypatch.setattr(ledger, "msvcrt", None)
        expected = "lock_" + failure
    if failure == "timeout":
        def busy(*args):
            raise OSError(ledger.errno.EACCES, "PRIVATE_EXCEPTION_TEXT")
        monkeypatch.setattr(ledger, "msvcrt", SimpleNamespace(locking=busy, LK_NBLCK=1))
        monkeypatch.setattr(ledger, "WINDOWS_LOCK_TIMEOUT_SECONDS", 0)
    if failure in {"storage", "unexpected"}:
        def fail_write(*args):
            error = OSError if failure == "storage" else RuntimeError
            raise error("PRIVATE_EXCEPTION_TEXT")
        monkeypatch.setattr(ledger, "write_json_atomic", fail_write)
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    assert result == {"systemMessage": "Session Ledger: " + ledger.NOTICE_TEXT[expected]}
    assert not ledger.record_path(tmp_path, "synthetic-session").exists()


def test_rolling_retention_notice_and_failed_write_do_not_claim_saved_trimming(
    tmp_path, monkeypatch, capsys
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path), "prompt": "x" * 20000}
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    assert result == {"systemMessage": "Session Ledger: " + ledger.NOTICE_TEXT["retention"]}
    path = ledger.record_path(tmp_path, "synthetic-session")
    original = path.read_bytes()
    assert ledger.ENTRY_TRUNCATION_MARKER in json.loads(original)["entries"][0]["text"]
    def fail_write(*args):
        raise OSError("PRIVATE_EXCEPTION_TEXT")
    monkeypatch.setattr(ledger, "write_json_atomic", fail_write)
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path, {**payload, "prompt": "y" * 20000})
    assert result == {"systemMessage": "Session Ledger: " + ledger.NOTICE_TEXT["storage"]}
    assert path.read_bytes() == original


def test_rolling_eviction_is_reported(tmp_path, monkeypatch, capsys):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path)}
    for index in range(8):
        result = invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                             {**payload, "prompt": str(index) * 12000})
    assert ledger.NOTICE_TEXT["retention"] in result["systemMessage"]
    record = json.loads(ledger.record_path(tmp_path, "synthetic-session").read_text())
    assert len(record["entries"]) < 8


def test_restore_notice_shares_one_bounded_json_response(tmp_path, monkeypatch, capsys):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "compact_summary": "x" * 50000}
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload, "post-compact")
    assert ledger.NOTICE_TEXT["summary"] in result["systemMessage"]
    path = ledger.record_path(tmp_path, "synthetic-session")
    original = path.read_bytes()
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                         {**payload, "source": "resume"}, "session-start")
    assert ledger.NOTICE_TEXT["restore"] in result["systemMessage"]
    assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert len(json.dumps(result)) <= ledger.HOST_CONTEXT_CHARACTER_BUDGET
    assert path.read_bytes() == original


def start_writer(root, label, unlocked):
    return subprocess.Popen(
        [sys.executable, "-c", WORKER, str(HOOK), str(root), label, str(unlocked)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.mark.parametrize(
    "unlocked", [False, True], ids=["serialized", "negative-control"]
)
def test_concurrent_captures_keep_both_updates(tmp_path, unlocked):
    first = start_writer(tmp_path, "Synthetic first", unlocked)
    second = None
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        assert pool.submit(first.stdout.readline).result(timeout=5) == "read\n"
        second = start_writer(tmp_path, "Synthetic second", unlocked)
        second_read = pool.submit(second.stdout.readline)
        if unlocked:
            assert second_read.result(timeout=5) == "read\n"
        else:
            with pytest.raises(TimeoutError):
                second_read.result(timeout=0.2)
        first.stdin.write("continue\n")
        first.stdin.flush()
        assert first.wait(timeout=5) == 0, first.stderr.read()
        assert second_read.result(timeout=5) == "read\n"
        second.stdin.write("continue\n")
        second.stdin.flush()
        assert second.wait(timeout=5) == 0, second.stderr.read()
    finally:
        for process in (first, second):
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()
        pool.shutdown(wait=True)
    ledger = load_ledger()
    record = json.loads(ledger.record_path(tmp_path, "synthetic-session").read_text())
    expected = (
        ["Synthetic second"] if unlocked else ["Synthetic first", "Synthetic second"]
    )
    assert [entry["text"] for entry in record["entries"]] == expected


def test_unknown_lock_backend_skips_update_instead_of_writing_unlocked(
    tmp_path, monkeypatch
):
    ledger = load_ledger()
    monkeypatch.setattr(ledger, "fcntl", None)
    monkeypatch.setattr(ledger, "msvcrt", None, raising=False)
    assert not ledger.update_ledger(
        {
            "session_id": "synthetic-session",
            "cwd": str(tmp_path),
            "prompt": "Synthetic",
        },
        data_root=tmp_path,
    )
    assert not ledger.record_path(tmp_path, "synthetic-session").exists()


def test_orphan_cleanup_preserves_held_lock_then_removes_it(tmp_path):
    ledger = load_ledger()
    path = ledger.lock_path(tmp_path, "synthetic-session")
    with ledger.session_lock(tmp_path, "synthetic-session"):
        ledger.remove_unheld_lock(path)
        assert path.exists()
    ledger.remove_unheld_lock(path)
    assert not path.exists()


def test_windows_lock_timeout_skips_write_and_closes_descriptor(tmp_path, monkeypatch):
    import errno
    import os
    from types import SimpleNamespace

    ledger = load_ledger()
    closed = []
    original_close = os.close

    def busy(descriptor, mode, length):
        assert mode == 1 and length == 1
        raise OSError(errno.EACCES, "synthetic contention")

    def close(descriptor):
        closed.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(ledger, "fcntl", None)
    monkeypatch.setattr(ledger, "msvcrt", SimpleNamespace(locking=busy, LK_NBLCK=1))
    monkeypatch.setattr(ledger, "WINDOWS_LOCK_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(ledger.os, "close", close)
    assert not ledger.update_ledger(
        {
            "session_id": "synthetic-session",
            "cwd": str(tmp_path),
            "prompt": "Synthetic",
        },
        data_root=tmp_path,
    )
    assert len(closed) == 1
    assert not ledger.record_path(tmp_path, "synthetic-session").exists()


def test_process_exit_releases_lock_for_next_capture(tmp_path):
    writer = start_writer(tmp_path, "Synthetic interrupted", False)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        assert pool.submit(writer.stdout.readline).result(timeout=5) == "read\n"
    finally:
        writer.kill()
        writer.wait(timeout=5)
        pool.shutdown(wait=True)
        for stream in (writer.stdin, writer.stdout, writer.stderr):
            stream.close()
    ledger = load_ledger()
    assert ledger.update_ledger(
        {
            "session_id": "synthetic-session",
            "cwd": str(tmp_path),
            "prompt": "Synthetic next",
        },
        data_root=tmp_path,
    )


def test_windows_lock_retries_contention_then_releases_same_byte(tmp_path, monkeypatch):
    import errno
    import os
    from types import SimpleNamespace

    ledger = load_ledger()
    calls = []

    def locking(descriptor, mode, length):
        calls.append((mode, length, os.lseek(descriptor, 0, os.SEEK_CUR)))
        if len(calls) == 1:
            raise OSError(errno.EACCES, "synthetic contention")

    monkeypatch.setattr(ledger, "fcntl", None)
    monkeypatch.setattr(
        ledger, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=1, LK_UNLCK=2)
    )
    with ledger.session_lock(tmp_path, "synthetic-session"):
        pass
    assert calls == [(1, 1, 0), (1, 1, 0), (2, 1, 0)]


@pytest.mark.parametrize(
    "raw", [b"\xff", b"[" * 10_000 + b"0" + b"]" * 10_000],
    ids=["invalid-utf8", "deep-json"],
)
def test_corrupt_session_does_not_prevent_other_session_start(tmp_path, raw):
    ledger = load_ledger()
    first = {"session_id": "synthetic-corrupt", "cwd": str(tmp_path)}
    second = {"session_id": "synthetic-independent", "cwd": str(tmp_path)}
    assert ledger.initialize_session(first, data_root=tmp_path)
    ledger.record_path(tmp_path, first["session_id"]).write_bytes(raw)
    assert ledger.initialize_session(second, data_root=tmp_path)
    assert ledger.record_path(tmp_path, second["session_id"]).is_file()
    assert not ledger.record_path(tmp_path, first["session_id"]).exists()


def test_pruning_skips_active_writer_then_rechecks_refreshed_expiry(tmp_path):
    ledger = load_ledger()
    now = datetime.now(timezone.utc)
    payload = {"session_id": "synthetic-prune-race", "cwd": str(tmp_path)}
    assert ledger.initialize_session(payload, data_root=tmp_path, now=now-timedelta(days=31))
    worker = r'''
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("ledger", sys.argv[1])
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)
root = Path(sys.argv[2])
payload = {"session_id": "synthetic-prune-race", "cwd": str(root), "prompt": "fresh synthetic"}
with ledger.session_lock(root, payload["session_id"]):
    print("locked", flush=True)
    sys.stdin.readline()
    assert ledger.update_current_ledger(payload, root, ledger.utc_now())
'''
    process = subprocess.Popen(
        [sys.executable, "-c", worker, str(HOOK), str(tmp_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        ledger.prune_expired(tmp_path, now)
        assert ledger.record_path(tmp_path, payload["session_id"]).exists()
    finally:
        stdout, stderr = process.communicate("continue\n", timeout=10)
    assert process.returncode == 0, stderr
    ledger.prune_expired(tmp_path, now)
    record = ledger.read_json(ledger.record_path(tmp_path, payload["session_id"]))
    assert record is not None
    assert record["entries"][0]["text"] == "fresh synthetic"


@pytest.mark.parametrize("mode", ["transcript", "hook-first", "scrambled"])
def test_full_history_replay_is_stable_and_new_turns_still_append(
    tmp_path, monkeypatch, capsys, mode
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-replay", "cwd": str(tmp_path)}
    texts = [f"Synthetic message {index}: " + str(index) * 12000 for index in range(8)]
    transcript = tmp_path / "synthetic.jsonl"
    lines = [json.dumps({"uuid": f"synthetic-{index}", "message": {
        "role": "assistant", "content": text}}) for index, text in enumerate(texts)]
    if mode == "hook-first":
        for text in texts:
            invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                        {**payload, "last_assistant_message": text})
    transcript.write_text("\n".join(lines), encoding="utf-8")
    payload["transcript_path"] = str(transcript)
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    path = ledger.record_path(tmp_path, "synthetic-replay")
    if mode == "scrambled":
        record = json.loads(path.read_bytes())
        record["entries"] = record["entries"][2:] + record["entries"][:2]
        path.write_text(json.dumps(record), encoding="utf-8")
        # Repair changes stored chronology and may report trimming once.
        invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    expected = texts[-5:]
    for _ in range(3):
        assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
        record = json.loads(path.read_bytes())
        assert [entry["text"] for entry in record["entries"]] == expected
    before = path.read_bytes()
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    assert path.read_bytes() == before
    new_text = "Synthetic newest message: " + "n" * 12000
    lines.append(json.dumps({"uuid": "synthetic-new", "message": {
        "role": "assistant", "content": new_text}}))
    transcript.write_text("\n".join(lines), encoding="utf-8")
    result = invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    assert ledger.NOTICE_TEXT["retention"] in result["systemMessage"]
    record = json.loads(path.read_bytes())
    assert [entry["text"] for entry in record["entries"]] == [*texts[-4:], new_text]
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}


@pytest.mark.parametrize("message_size", [20, 13000])
def test_first_transcript_capture_does_not_discard_unseen_earlier_text(
    tmp_path, monkeypatch, capsys, message_size
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-backfill", "cwd": str(tmp_path)}
    invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                {**payload, "last_assistant_message": "Synthetic latest"})
    transcript = tmp_path / "synthetic.jsonl"
    texts = [f"Synthetic earlier {i}: " + str(i) * message_size for i in range(6)]
    texts.append("Synthetic latest")
    transcript.write_text("\n".join(json.dumps({"message": {
        "role": "assistant", "content": text}}) for text in texts), encoding="utf-8")
    payload["transcript_path"] = str(transcript)
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    path = ledger.record_path(tmp_path, "synthetic-backfill")
    record = json.loads(path.read_bytes())
    expected = ledger.bounded_entries(ledger.transcript_entries(transcript.read_text(encoding="utf-8")))
    assert [entry["text"] for entry in record["entries"]] == [entry["text"] for entry in expected]
    assert len(record["entries"]) > 1
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    assert json.loads(path.read_bytes())["entries"] == record["entries"]


def test_history_survives_summary_missing_tail_and_replacement(
    tmp_path, monkeypatch, capsys
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-cursor", "cwd": str(tmp_path)}
    transcript = tmp_path / "synthetic.jsonl"
    transcript.write_text(json.dumps({"message": {
        "role": "assistant", "content": "Synthetic old"}}), encoding="utf-8")
    payload["transcript_path"] = str(transcript)
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    path = ledger.record_path(tmp_path, "synthetic-cursor")
    original = json.loads(path.read_bytes())["entries"][0]
    invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                {**payload, "compact_summary": "Synthetic summary"}, "post-compact")
    transcript.unlink()
    invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                {**payload, "prompt": "Synthetic between"})
    assert json.loads(path.read_bytes())["entries"][0] == original
    transcript.write_text(json.dumps({"message": {
        "role": "assistant", "content": "Synthetic after compaction"}}), encoding="utf-8")
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    record = json.loads(path.read_bytes())
    assert [entry["text"] for entry in record["entries"]] == [
        "Synthetic old", "Synthetic between", "Synthetic after compaction"]


def test_failed_write_preserves_history_for_retry(tmp_path, monkeypatch, capsys):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-retry", "cwd": str(tmp_path)}
    transcript = tmp_path / "synthetic.jsonl"
    transcript.write_text(json.dumps({"message": {
        "role": "assistant", "content": "Synthetic first"}}), encoding="utf-8")
    payload["transcript_path"] = str(transcript)
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    path = ledger.record_path(tmp_path, "synthetic-retry")
    before = path.read_bytes()
    with transcript.open("a", encoding="utf-8") as stream:
        stream.write("\n" + json.dumps({"message": {
            "role": "assistant", "content": "Synthetic retry"}}))
    with monkeypatch.context() as patch:
        def fail_write(*args):
            raise OSError("Synthetic failure")
        patch.setattr(ledger, "write_json_atomic", fail_write)
        result = invoke_hook(ledger, patch, capsys, tmp_path, payload)
        assert ledger.NOTICE_TEXT["storage"] in result["systemMessage"]
    assert path.read_bytes() == before
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    assert json.loads(path.read_bytes())["entries"][-1]["text"] == "Synthetic retry"


def test_first_transcript_preserves_interleaved_hook_correction(tmp_path, monkeypatch, capsys):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-interleaved", "cwd": str(tmp_path)}
    texts = ["Synthetic A", "Synthetic correction E", "Synthetic B"]
    for text in texts:
        invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                    {**payload, "last_assistant_message": text})
    transcript = tmp_path / "synthetic.jsonl"
    transcript.write_text("\n".join(json.dumps({"message": {
        "role": "assistant", "content": text}}) for text in [texts[0], texts[2]]), encoding="utf-8")
    payload["transcript_path"] = str(transcript)
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    record = json.loads(ledger.record_path(tmp_path, "synthetic-interleaved").read_bytes())
    assert [entry["text"] for entry in record["entries"]] == texts


def test_later_transcript_row_stays_after_trailing_hook_correction(tmp_path, monkeypatch, capsys):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-trailing-correction", "cwd": str(tmp_path)}
    for text in ("Synthetic A", "Synthetic correction E"):
        invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                    {**payload, "last_assistant_message": text})
    transcript = tmp_path / "synthetic.jsonl"
    first = json.dumps({"uuid": "a", "message": {"role": "assistant", "content": "Synthetic A"}})
    second = json.dumps({"uuid": "b", "message": {"role": "assistant", "content": "Synthetic B"}})
    transcript.write_text(first, encoding="utf-8")
    payload["transcript_path"] = str(transcript)
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    transcript.write_text(first + "\n" + second, encoding="utf-8")
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    path = ledger.record_path(tmp_path, payload["session_id"])
    assert [entry["text"] for entry in json.loads(path.read_bytes())["entries"]] == [
        "Synthetic A", "Synthetic correction E", "Synthetic B"]


def test_interim_crlf_fingerprint_replays_without_duplicate():
    ledger = load_ledger()
    first = json.dumps({"uuid": "a", "message": {"role": "assistant", "content": "Synthetic A"}})
    second = json.dumps({"uuid": "b", "message": {"role": "assistant", "content": "Synthetic B"}})
    stored = [{"role": "assistant", "text": "Synthetic A", "fingerprint": ledger.digest(first + "\r")}]
    discovered = ledger.transcript_entries(first + "\r\n" + second + "\r\n")
    merged = ledger.reconciled_transcript_entries(stored, discovered, [])
    assert [entry["text"] for entry in merged] == ["Synthetic A", "Synthetic B"]
    assert merged[0]["fingerprint"] == stored[0]["fingerprint"]
    assert all(set(entry) == {"role", "text", "fingerprint"} for entry in merged)
    assert ledger.reconciled_transcript_entries(merged, discovered, []) == merged


@pytest.mark.parametrize("latest_in_transcript", [True, False])
def test_repeated_current_prompt_stays_after_intervening_answer(
    tmp_path, monkeypatch, capsys, latest_in_transcript
):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-repeat-order", "cwd": str(tmp_path)}
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, {**payload, "prompt": "Synthetic A"})
    invoke_hook(ledger, monkeypatch, capsys, tmp_path,
                {**payload, "last_assistant_message": "Synthetic B"})
    rows = [("user", "Synthetic A"), ("assistant", "Synthetic B")]
    if latest_in_transcript:
        rows.append(("user", "Synthetic A"))
    transcript = tmp_path / "synthetic.jsonl"
    transcript.write_text("\n".join(json.dumps({"uuid": str(index), "message": {
        "role": role, "content": text}}) for index, (role, text) in enumerate(rows)), encoding="utf-8")
    payload.update(transcript_path=str(transcript), prompt="Synthetic A")
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    path = ledger.record_path(tmp_path, "synthetic-repeat-order")
    assert [entry["text"] for entry in json.loads(path.read_bytes())["entries"]] == [
        "Synthetic A", "Synthetic B", "Synthetic A"]
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}
    assert [entry["text"] for entry in json.loads(path.read_bytes())["entries"]] == [
        "Synthetic A", "Synthetic B", "Synthetic A"]


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
def test_appending_row_preserves_prior_fingerprint(tmp_path, monkeypatch, capsys, ending):
    ledger = load_ledger()
    payload = {"session_id": "synthetic-line-ending", "cwd": str(tmp_path)}
    transcript = tmp_path / "synthetic.jsonl"
    rows = [json.dumps({"uuid": str(i), "message": {
        "role": "assistant", "content": text}}) for i, text in enumerate(["A", "B", "C"])]
    transcript.write_bytes(ending.join(rows[:2]).encode())
    payload["transcript_path"] = str(transcript)
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    transcript.write_bytes(ending.join(rows).encode())
    invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload)
    record = ledger.read_json(ledger.record_path(tmp_path, payload["session_id"]))
    assert [entry["text"] for entry in record["entries"]] == ["A", "B", "C"]
    assert invoke_hook(ledger, monkeypatch, capsys, tmp_path, payload) == {}


def test_duplicate_raw_row_does_not_overwrite_intervening_message():
    ledger = load_ledger()
    row_a = json.dumps({"uuid": "same-row", "message": {"role": "assistant", "content": "A"}})
    row_b = json.dumps({"uuid": "other-row", "message": {"role": "assistant", "content": "B"}})
    transcript = "\n".join([row_a, row_b, row_a])
    hooks = ledger.hook_payload_entries({"last_assistant_message": "A"}, transcript)
    entries = ledger.reconciled_transcript_entries([], ledger.transcript_entries(transcript), hooks)
    assert [entry["text"] for entry in entries] == ["A", "B"]
