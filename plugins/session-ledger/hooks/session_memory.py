"""Experimental local evidence index; no network or model inference.

Bodies preserve the JSON value logged by the host, not provider completeness.
All callers must hold the ledger's session lock and validate the session scope.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_BATCH_BYTES = 8 * 1024 * 1024
PAGE_CHARACTERS = 2048
RETENTION_SECONDS = 30 * 24 * 3600
KINDS = ("decision", "correction", "scope", "definition", "provenance", "artifact", "checkpoint")


def encoded(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tool_events(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract only host tool blocks; ordinary conversation is not archived."""
    events = []
    message = row.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), list):
        for block in message["content"]:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                events.append({"kind": "call", "call_id": block.get("id"),
                               "name": block.get("name", ""), "body": block})
            elif kind == "tool_result":
                body = dict(block)
                if "toolUseResult" in row:
                    count = sum(isinstance(item, dict) and item.get("type") == "tool_result" for item in message["content"])
                    field = "host_tool_result" if count == 1 else "unassigned_host_tool_result"
                    body[field] = row["toolUseResult"]
                events.append({"kind": "result", "call_id": block.get("tool_use_id"),
                               "name": "", "body": body})
    payload = row.get("payload")
    if row.get("type") == "response_item" and isinstance(payload, dict):
        kind = payload.get("type")
        if kind in ("function_call", "custom_tool_call"):
            events.append({"kind": "call", "call_id": payload.get("call_id"),
                           "name": payload.get("name", ""), "body": payload})
        elif kind in ("function_call_output", "custom_tool_call_output"):
            events.append({"kind": "result", "call_id": payload.get("call_id"),
                           "name": "", "body": payload})
    for event in events:
        if not isinstance(event["call_id"], str) or not event["call_id"] or not isinstance(event["name"], str):
            raise ValueError("invalid_tool_identity")
    return events


def after_cutoff(stamp: Any, cutoff: str) -> bool:
    if not cutoff:
        return True
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        boundary = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        return bool(moment.tzinfo and boundary.tzinfo and moment.astimezone(timezone.utc) > boundary)
    except (AttributeError, TypeError, ValueError):
        return False


def row_session(row: dict[str, Any]) -> str | None:
    """Return explicit host identity; never infer it from text or tool data."""
    for key in ("sessionId", "session_id"):
        if isinstance(row.get(key), str):
            return row[key]
    payload = row.get("payload")
    if row.get("type") == "session_meta" and isinstance(payload, dict):
        return payload.get("id") if isinstance(payload.get("id"), str) else None
    return None


class Store:
    """One session/plan database. SQLite commits evidence and offsets together."""

    def __init__(self, path: Path, session_id: str, plan_id: str, *, create: bool = False):
        if path.is_symlink() or (not create and not path.is_file()):
            raise ValueError("memory_not_enabled")
        if create and not path.exists():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        self.db = sqlite3.connect(str(path), timeout=0.15)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA secure_delete=ON")
            page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
            self.db.execute(f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page_size}")
            self._schema(session_id, plan_id, create)
            if create:
                with self.db:
                    self.db.execute("UPDATE meta SET value=? WHERE key='expires'", (str(time.time() + RETENTION_SECONDS),))
        except Exception:
            self.db.close()
            raise
        self.session_id = session_id
        self.path = path

    def _schema(self, session_id: str, plan_id: str, create: bool) -> None:
        if create:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS cursors(
                    source TEXT PRIMARY KEY, offset INTEGER, anchor TEXT, identity TEXT);
                CREATE TABLE IF NOT EXISTS events(
                    id TEXT PRIMARY KEY, call_id TEXT, kind TEXT, name TEXT, body TEXT,
                    timestamp TEXT, source TEXT, offset INTEGER, error INTEGER);
                CREATE INDEX IF NOT EXISTS event_calls ON events(call_id);
                CREATE TABLE IF NOT EXISTS states(
                    revision INTEGER PRIMARY KEY, key TEXT, kind TEXT, text TEXT,
                    evidence TEXT, previous INTEGER, timestamp REAL);
                CREATE INDEX IF NOT EXISTS state_keys ON states(key, revision);
            ''')
            with self.db:
                for key, value in (("session", sha(session_id.encode())), ("plan", plan_id),
                                   ("expires", str(time.time() + RETENTION_SECONDS)), ("schema", "1")):
                    self.db.execute("INSERT OR IGNORE INTO meta VALUES (?, ?)", (key, value))
            try:
                self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(name, body, content='events', content_rowid='rowid')")
            except sqlite3.OperationalError as exc:
                if "no such module" not in str(exc):
                    raise
        meta = dict(self.db.execute("SELECT key, value FROM meta"))
        if (meta.get("session") != sha(session_id.encode()) or meta.get("plan") != plan_id
                or meta.get("schema") != "1" or float(meta.get("expires", "0")) <= time.time()):
            raise ValueError("memory_scope_or_expiry")
        self.fts = bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='search'").fetchone())

    def close(self) -> None:
        self.db.close()

    def _insert_event(self, event: dict[str, Any], row: dict[str, Any], source: str, offset: int) -> None:
        if len(event["call_id"]) > 512 or len(event["name"]) > 256:
            raise ValueError("invalid_tool_identity")
        body = encoded(event["body"])
        identity = sha(encoded([event["kind"], event["call_id"], body]).encode())
        result = self.db.execute(
            "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (identity, event["call_id"], event["kind"], event["name"], body,
             str(row.get("timestamp", ""))[:64], source, offset,
             int(event["body"].get("is_error") is True)))
        if result.rowcount and self.fts:
            self.db.execute("INSERT INTO search(rowid, name, body) VALUES (?, ?, ?)",
                            (result.lastrowid, event["name"], body))

    def _read_batch(self, stream: Any, source: str, offset: int, *, cutoff: str) -> dict[str, Any]:
        read_bytes = 0
        rows = 0
        rejected = 0
        status = "caught_up"
        deadline = time.monotonic() + 1.0
        while read_bytes < MAX_BATCH_BYTES and time.monotonic() < deadline:
            start = stream.tell()
            line = stream.readline(MAX_LINE_BYTES + 1)
            read_bytes += len(line)
            if not line:
                break
            if len(line) > MAX_LINE_BYTES:
                status = "oversized_line"
                break
            if not line.endswith(b"\n"):
                status = "pending_partial_line"
                break
            try:
                row = json.loads(line.decode("utf-8"))
            except (ValueError, RecursionError):
                # Do not jump over unknown data: explicit repair can retry this offset.
                status = "invalid_line"
                break
            if not isinstance(row, dict):
                status = "invalid_line"
                break
            identity = row_session(row)
            if identity is not None and identity != self.session_id:
                raise ValueError("transcript_session_mismatch")
            stamp = row.get("timestamp")
            # For explicit plan boundaries fail closed on absent/invalid timestamps.
            if not after_cutoff(stamp, cutoff):
                rejected += 1
            else:
                for event in tool_events(row):
                    self._insert_event(event, row, source, start)
            offset = stream.tell()
            rows += 1
        else:
            status = "more_pending"
        return {"status": status, "offset": offset, "bytes_read": read_bytes,
                "rows": rows, "rows_excluded_by_plan": rejected}

    def _verify_source(self, stream: Any) -> int:
        """Require an explicit host session identity before trusting the source."""
        size = 0
        for _ in range(1024):
            line = stream.readline(256 * 1024 - size + 1)
            size += len(line)
            if not line or size > 256 * 1024:
                break
            try:
                row = json.loads(line.decode("utf-8"))
            except (ValueError, RecursionError):
                raise ValueError("transcript_identity_unavailable") from None
            if isinstance(row, dict):
                identity = row_session(row)
                if identity is not None:
                    if identity != self.session_id:
                        raise ValueError("transcript_session_mismatch")
                    return size
                if tool_events(row):
                    break
        raise ValueError("transcript_identity_unavailable")

    def sync(self, transcript: Path, *, cutoff: str = "") -> dict[str, Any]:
        """Incrementally ingest one explicitly scoped transcript; no directory scans."""
        if transcript.is_symlink() or not transcript.is_file():
            raise ValueError("transcript_unavailable")
        source = sha(str(transcript.absolute()).encode())
        cursor = self.db.execute("SELECT * FROM cursors WHERE source=?", (source,)).fetchone()
        with transcript.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            identity = f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}"
            offset = cursor["offset"] if cursor else 0
            anchor_start = max(0, offset - 4096)
            stream.seek(anchor_start)
            anchor = sha(stream.read(offset - anchor_start))
            previous = cursor["identity"].split(":") if cursor else []
            changed_file = bool(previous and (previous[:2] != identity.split(":")[:2]
                                or (int(previous[2]) == stat.st_size and previous[3] != str(stat.st_mtime_ns))))
            reset = bool(cursor and (changed_file or stat.st_size < offset or cursor["anchor"] != anchor))
            identity_bytes = 0
            if not cursor or reset:
                stream.seek(0)
                identity_bytes = self._verify_source(stream)
            if reset:
                offset = 0
            stream.seek(offset)
            with self.db:
                result = self._read_batch(stream, source, offset, cutoff=cutoff)
                offset = result["offset"]
                stream.seek(max(0, offset - 4096))
                anchor = sha(stream.read(min(offset, 4096)))
                self.db.execute("INSERT OR REPLACE INTO cursors VALUES (?, ?, ?, ?)",
                                (source, offset, anchor, identity))
                if result["rows"]:
                    self.db.execute("UPDATE meta SET value=? WHERE key='expires'",
                                    (str(time.time() + RETENTION_SECONDS),))
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('last_sync', ?)", (encoded(result),))
            return {**result, "cursor_reset": reset, "identity_bytes_read": identity_bytes, "anchor_bytes_read": min(cursor["offset"], 4096) if cursor else 0}

    def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError("invalid_search")
        limit = max(1, min(limit, 20))
        tokens = re.findall(r"\w+", query, re.UNICODE)[:8]
        if not tokens:
            raise ValueError("invalid_search")
        if self.fts:
            expression = " AND ".join('"' + token + '"' for token in tokens)
            rows = self.db.execute(
                "SELECT e.id, e.call_id, e.kind, e.name, e.timestamp, e.error, substr(e.body,1,240) preview "
                "FROM search JOIN events e ON e.rowid=search.rowid WHERE search MATCH ? LIMIT ?",
                (expression, limit + 1)).fetchall()
        else:
            clauses = " AND ".join("(name || ' ' || body) LIKE ? ESCAPE '\\'" for _ in tokens)
            patterns = ["%" + token.replace("_", "\\_") + "%" for token in tokens]
            rows = self.db.execute(
                "SELECT id, call_id, kind, name, timestamp, error, substr(body,1,240) preview "
                f"FROM events WHERE {clauses} ORDER BY rowid LIMIT ?", (*patterns, limit + 1)).fetchall()
        return {"matches": [dict(row) for row in rows[:limit]], "more": len(rows) > limit,
                "search_mode": "fts5" if self.fts else "literal_scan", "transcript_bytes_read": 0,
                "trust": "untrusted historical evidence; completeness and current validity unknown"}

    def fetch(self, identity: str, *, start: int = 0, pointer: str = "") -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM events WHERE id=?", (identity,)).fetchone()
        if not row:
            raise ValueError("evidence_not_found")
        body = row["body"]
        if sha(encoded([row["kind"], row["call_id"], body]).encode()) != identity:
            raise ValueError("evidence_hash_mismatch")
        selected = body
        if pointer:
            value = json.loads(body)
            if not pointer.startswith("/") or len(pointer) > 512:
                raise ValueError("invalid_pointer")
            try:
                for token in pointer[1:].split("/"):
                    if re.search(r"~(?![01])", token):
                        raise ValueError("invalid_pointer")
                    key = token.replace("~1", "/").replace("~0", "~")
                    if isinstance(value, list) and not re.fullmatch(r"0|[1-9][0-9]*", key):
                        raise ValueError("invalid_pointer")
                    value = value[int(key)] if isinstance(value, list) else value[key]
            except (KeyError, IndexError, TypeError, ValueError):
                raise ValueError("pointer_not_found") from None
            selected = encoded(value)
        if start < 0 or start > len(selected):
            raise ValueError("invalid_page")
        links = self.db.execute("SELECT id, kind, error FROM events WHERE call_id=? ORDER BY rowid LIMIT 21",
                                (row["call_id"],)).fetchall()
        calls = sum(link["kind"] == "call" for link in links)
        results = sum(link["kind"] == "result" for link in links)
        pairing = "ambiguous" if calls > 1 or results > 1 or len(links) > 20 else (
            "paired" if calls == results == 1 else "missing_call" if not calls else "missing_result")
        return {"id": identity, "call_id": row["call_id"], "kind": row["kind"],
                "timestamp": row["timestamp"], "sha256": sha(body.encode()), "pairing": pairing,
                "links": [dict(link) for link in links[:20]], "host_error": bool(row["error"]),
                "completeness": "unknown; only logged data preserved", "freshness": "historical; reverify for current claims",
                "pointer": pointer, "start": start, "text": selected[start:start + PAGE_CHARACTERS],
                "next": start + PAGE_CHARACTERS if start + PAGE_CHARACTERS < len(selected) else None,
                "total_characters": len(selected), "transcript_bytes_read": 0}

    def remember(self, key: str, kind: str, text: str, evidence: list[str], expected: int = 0) -> int:
        if (kind not in KINDS or not isinstance(key, str) or not 0 < len(key) <= 128
                or not isinstance(text, str) or not 0 < len(text) <= 4096
                or not isinstance(evidence, list) or len(evidence) > 20
                or any(not isinstance(item, str) for item in evidence)):
            raise ValueError("invalid_state")
        with self.db:
            previous = self.db.execute("SELECT max(revision) FROM states WHERE key=?", (key,)).fetchone()[0] or 0
            if previous != expected:
                raise ValueError("state_revision_conflict")
            for identity in evidence:
                if not self.db.execute("SELECT 1 FROM events WHERE id=?", (identity,)).fetchone():
                    raise ValueError("state_evidence_not_found")
            result = self.db.execute("INSERT INTO states(key,kind,text,evidence,previous,timestamp) VALUES (?,?,?,?,?,?)",
                                     (key, kind, text, encoded(evidence), previous, time.time()))
            self.db.execute("UPDATE meta SET value=? WHERE key='expires'", (str(time.time() + RETENTION_SECONDS),))
            return result.lastrowid

    def state(self, *, before: int = 0, limit: int = 10, revision: int = 0) -> dict[str, Any]:
        limit = max(1, min(limit, 20))
        rows = self.db.execute(
            "SELECT * FROM states WHERE revision IN (SELECT max(revision) FROM states GROUP BY key) "
            "AND (?=0 OR revision<?) ORDER BY revision DESC LIMIT ?", (before, before, limit + 1)).fetchall()
        if revision:
            rows = self.db.execute("SELECT * FROM states WHERE revision=?", (revision,)).fetchall()
        items = []
        for row in rows[:limit]:
            item = dict(row)
            item["evidence"] = json.loads(item["evidence"])
            items.append(item)
        return {"items": items, "next": items[-1]["revision"] if len(rows) > limit else None,
                "trust": "explicitly recorded historical state, not independently verified"}

    def status(self) -> dict[str, Any]:
        return {"events": self.db.execute("SELECT count(*) FROM events").fetchone()[0],
                "state_revisions": self.db.execute("SELECT count(*) FROM states").fetchone()[0],
                "last_sync": json.loads(dict(self.db.execute("SELECT key,value FROM meta")).get("last_sync", "null")),
                "database_bytes": self.path.stat().st_size, "quota_bytes": MAX_DATABASE_BYTES,
                "search_mode": "fts5" if self.fts else "literal_scan", "scope": "current session and plan",
                "expires_at_unix": float(self.db.execute("SELECT value FROM meta WHERE key='expires'").fetchone()[0])}
