#!/usr/bin/env python3
"""Small, independent session/plan lifecycle for Evidence Memory."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

SCHEMA_VERSION = 1
RETENTION_DAYS = 30
HOST_CONTEXT_CHARACTER_BUDGET = 9500
MEMORY_FILES = ("memory.sqlite3", "memory.sqlite3-journal", "memory.sqlite3-wal", "memory.sqlite3-shm")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def expires_at(now: datetime) -> datetime:
    return now + timedelta(days=RETENTION_DAYS)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def data_directory() -> Path | None:
    value = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(value) if value else None


def state_directory(root: Path) -> Path:
    return root / "evidence-memory"


def session_directory(root: Path, session_id: str) -> Path:
    return state_directory(root) / "sessions" / digest(session_id)


def record_path(root: Path, session_id: str) -> Path:
    return session_directory(root, session_id) / "record.json"


def scope_path(root: Path, session_id: str) -> Path:
    return session_directory(root, session_id) / "scope.json"


def state_paths_are_safe(root: Path, session_id: str | None = None) -> bool:
    paths = [root, state_directory(root), state_directory(root) / "sessions",
             state_directory(root) / "locks"]
    if session_id:
        paths.append(session_directory(root, session_id))
        paths.extend((record_path(root, session_id), scope_path(root, session_id)))
        paths.extend(session_directory(root, session_id) / name for name in MEMORY_FILES)
    return not any(path.is_symlink() for path in paths)


def secure_directory(path: Path) -> None:
    if path.is_symlink():
        raise OSError("unsafe_memory_path")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise OSError("unsafe_memory_path")
    if os.name == "posix":
        path.chmod(0o700)


def secure_parent(path: Path) -> None:
    root = path.parents[3]
    for directory in (root, root / "evidence-memory", root / "evidence-memory" / "sessions", path.parent):
        secure_directory(directory)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    secure_parent(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".evidence-memory-", suffix=".tmp", dir=path.parent)
    try:
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def is_current(payload: dict[str, Any], now: datetime) -> bool:
    expiry = parse_timestamp(payload.get("expires_at"))
    return payload.get("schema_version") == SCHEMA_VERSION and expiry is not None and expiry > now


def session_identity(payload: dict[str, Any], root: Path, now: datetime) -> tuple[str, str, str] | None:
    session_id, cwd = payload.get("session_id"), payload.get("cwd")
    if not isinstance(session_id, str) or not session_id or not isinstance(cwd, str) or not cwd:
        return None
    if not state_paths_are_safe(root, session_id):
        return None
    record = read_json(record_path(root, session_id))
    scope = read_json(scope_path(root, session_id))
    for saved in (scope, record):
        if saved and is_current(saved, now) and saved.get("session_hash") == digest(session_id):
            workspace = saved.get("workspace_hash")
            if isinstance(workspace, str) and workspace:
                plan = scope.get("plan_id") if scope and is_current(scope, now) else "default"
                return session_id, workspace, plan if isinstance(plan, str) and plan else "default"
    workspace = digest(os.path.normcase(str(Path(cwd).expanduser().resolve(strict=False))))
    return session_id, workspace, "default"


def record_for(*, workspace_hash: str, plan_id: str, now: datetime,
               session_id: str = "") -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "session_hash": digest(session_id),
            "workspace_hash": workspace_hash, "plan_id": plan_id,
            "compact_summary": "", "expires_at": timestamp(expires_at(now))}


def load_current_record(payload: dict[str, Any], *, data_root: Path, now: datetime) -> dict[str, Any] | None:
    identity = session_identity(payload, data_root, now)
    if not identity:
        return None
    session_id, workspace, plan = identity
    scope_file = scope_path(data_root, session_id)
    if scope_file.exists():
        scope = read_json(scope_file)
        if not scope or not is_current(scope, now) or scope.get("session_hash") != digest(session_id):
            return None
    record = read_json(record_path(data_root, session_id))
    if (record and is_current(record, now) and record.get("session_hash") == digest(session_id)
            and record.get("workspace_hash") == workspace and record.get("plan_id") == plan):
        return record
    return None


def refresh_plan_scope(root: Path, session_id: str, workspace: str, plan: str, now: datetime) -> None:
    scope = read_json(scope_path(root, session_id))
    if not scope or not is_current(scope, now) or scope.get("plan_id") != plan:
        return
    scope["expires_at"] = timestamp(expires_at(now))
    write_json_atomic(scope_path(root, session_id), scope)


def write_fresh_plan_scope(root: Path, session_id: str, workspace: str, now: datetime,
                           *, capture_paused: bool = False) -> None:
    """Commit a new cutoff before any old database can be reopened."""
    write_json_atomic(scope_path(root, session_id), {
        "schema_version": SCHEMA_VERSION,
        "session_hash": digest(session_id),
        "workspace_hash": workspace,
        "plan_id": uuid.uuid4().hex,
        "started_at": timestamp(now),
        "expires_at": timestamp(expires_at(now)),
        "capture_paused": capture_paused,
    })


def initialize_session(payload: dict[str, Any], *, data_root: Path | None = None) -> bool:
    root = data_root or data_directory()
    if not root:
        return False
    now = utc_now()
    identity = session_identity(payload, root, now)
    if not identity:
        return False
    session_id, workspace, plan = identity
    existing = load_current_record(payload, data_root=root, now=now)
    if existing:
        return True
    directory = session_directory(root, session_id)
    if not state_paths_are_safe(root, session_id):
        return False
    prior_record = read_json(record_path(root, session_id))
    prior_scope = read_json(scope_path(root, session_id))
    current_scope = (prior_scope is not None and is_current(prior_scope, now)
                     and prior_scope.get("session_hash") == digest(session_id))
    scope_replaced = record_path(root, session_id).exists() and (
        prior_record is None or not is_current(prior_record, now))
    if not current_scope and (record_path(root, session_id).exists()
                              or scope_path(root, session_id).exists()):
        scope_replaced = True
    # A valid begin-plan cutoff survives its disabled interval. Expired or
    # corrupt prior metadata starts a fresh cutoff before any database reset.
    if scope_replaced and not (current_scope and prior_record is not None
                               and prior_record.get("plan_id") != prior_scope.get("plan_id")):
        write_fresh_plan_scope(root, session_id, workspace, now)
        plan = read_json(scope_path(root, session_id))["plan_id"]
    for name in MEMORY_FILES:
        remove_file(directory / name)
    write_json_atomic(record_path(root, session_id), record_for(
        workspace_hash=workspace, plan_id=plan, now=now, session_id=session_id))
    return True


def remove_file(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("unsafe_memory_path")
    try:
        path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def session_hash_lock(root: Path, session_hash: str, *, wait: bool = True) -> Iterator[None]:
    if not re.fullmatch(r"[0-9a-f]{64}", session_hash):
        raise ValueError("invalid_session")
    directory = state_directory(root) / "locks"
    for item in (root, state_directory(root), directory):
        secure_directory(item)
    path = directory / session_hash
    if path.is_symlink():
        raise OSError("unsafe_memory_path")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("unsafe_memory_path")
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        elif msvcrt is not None:
            deadline = time.monotonic() + 1
            while True:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if not wait or error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK) or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.025)
        else:
            raise OSError("lock_unavailable")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            elif msvcrt is not None:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(descriptor)


def escaped_for_context(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def emitted_context_length(value: str) -> int:
    return len(json.dumps({"hookSpecificOutput": {"additionalContext": value, "hookEventName": "SessionStart"}}))
