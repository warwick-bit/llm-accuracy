"""Cross-process ledger serialization, including a lost-update negative control."""

import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
def test_workspace_change_preserves_record_and_return_resumes_capture(tmp_path, action):
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

    assert not getattr(ledger, action)(other, data_root=tmp_path, now=now + timedelta(hours=1))
    assert path.read_bytes() == before
    assert ledger.session_start_context(
        {**other, "source": "resume"}, data_root=tmp_path, now=now
    ) is None

    assert ledger.update_ledger(
        {**original, "prompt": "Synthetic returned"}, data_root=tmp_path,
        now=now + timedelta(hours=2),
    )
    record = json.loads(path.read_text())
    assert record["created_at"] == json.loads(before)["created_at"]
    assert record["compact_summary"] == "Synthetic summary"
    assert [entry["text"] for entry in record["entries"]] == [
        "Synthetic first", "Synthetic returned"
    ]


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
def test_workspace_owner_is_rechecked_after_acquiring_lock(tmp_path, monkeypatch, action):
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
    assert not getattr(ledger, action)(payload, data_root=tmp_path, now=now)
    assert json.loads(ledger.record_path(tmp_path, "synthetic-session").read_text()) == owner


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
