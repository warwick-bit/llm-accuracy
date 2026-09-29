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
from typing import Any, Iterator

MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_BATCH_BYTES = 8 * 1024 * 1024
PAGE_CHARACTERS = 2048
RETENTION_SECONDS = 30 * 24 * 3600
KINDS = ("decision", "correction", "scope", "definition", "provenance", "artifact", "checkpoint")
CAPTURE_MODES = ("external", "all")
CAPTURE_COUNTERS = ("calls_out_of_scope", "calls_withheld_restricted", "results_without_stored_call",
                    "results_withheld_by_scope")
RECENT_RESULTS = 10
WEB_TOOLS = ("WebFetch", "WebSearch")
# Codex logs one outer JavaScript call; these references suggest, but do not prove, which inner tools ran.
CODEX_EXTERNAL_REFERENCE = re.compile(r"\btools\s*\.\s*(mcp__[\w-]+__[\w-]+|web__run)\s*\(")
MCP_TOOL_NAME = re.compile(r"mcp__[\w-]+__[\w-]+")
RESTRICTED_TOKENS = frozenset((
    "bank", "credential", "credentials", "employee", "employees", "hr", "leave", "passport", "password",
    "passwords", "payroll", "payslip", "payslips", "pension", "salaries", "salary", "secret", "secrets",
    "ssn", "superannuation", "tax", "timesheet", "timesheets"))


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


def name_tokens(name: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    # Also split an acronym from the word after it: getSSNProfile -> get SSN Profile.
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return {token.lower() for token in re.split(r"[^A-Za-z0-9]+", spaced) if token}


class CaptureScope:
    """Choose which logged tool calls to store, from tool names alone.

    Withholding is best effort: a tool with an innocuous name can still return
    sensitive content, and the local configuration is a preference, not a boundary.
    """

    def __init__(self, mode: str = "external", extra_restricted: tuple[str, ...] = ()):
        if mode not in CAPTURE_MODES:
            raise ValueError("invalid_capture_mode")
        self.mode = mode
        self.restricted = RESTRICTED_TOKENS | {token.lower() for token in extra_restricted}

    def listing(self) -> "CaptureScope":
        """The external rule with the same withholding; the recent-results index uses it in every mode."""
        return CaptureScope("external", tuple(self.restricted))

    def classify(self, event: dict[str, Any]) -> tuple[str, list[str]]:
        """Return capture, skip or withhold for one call, plus the external tools it references."""
        name, body = event["name"], event["body"]
        mentioned = [name] if name.startswith("mcp__") else []
        external = [name] if name.startswith("mcp__") or name in WEB_TOOLS else []
        code = (body.get("input") if body.get("type") == "custom_tool_call" else
                body.get("arguments") if body.get("type") == "function_call" else None)
        if isinstance(code, str):
            # Any restricted name in a mixed Codex cell withholds the whole cell.
            mentioned += MCP_TOOL_NAME.findall(code)
            external += [match.group(1) for match in CODEX_EXTERNAL_REFERENCE.finditer(code)]
        if any(name_tokens(item[len("mcp__"):]) & self.restricted for item in mentioned):
            return "withhold", []
        if external or self.mode == "all":
            return "capture", list(dict.fromkeys(external))
        return "skip", []


class Store:
    """One session/plan database. SQLite commits evidence and offsets together."""

    def __init__(self, path: Path, session_id: str, plan_id: str, *, create: bool = False, read_only: bool = False):
        if path.is_symlink() or (not create and not path.is_file()):
            raise ValueError("memory_not_enabled")
        if create and read_only:
            raise ValueError("invalid_store_mode")
        if create and not path.exists():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        # Read-only opens serve read actions in a host sandbox that refuses every write.
        self.read_only = read_only
        if read_only:
            self.db = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.15)
        else:
            self.db = sqlite3.connect(str(path), timeout=0.15)
        self.db.row_factory = sqlite3.Row
        try:
            if not read_only:
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
        # An enabled experimental index may predate local retrieval counters.
        try:
            if not self.read_only:
                with self.db:
                    self.db.execute("CREATE TABLE IF NOT EXISTS retrieval_counts("
                                    "outcome TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        except sqlite3.Error:
            # A full legacy index must remain readable even if counters cannot be added.
            pass
        # Indexes created before capture scoping keep their unscoped rows until cleared.
        if "capture_policy" not in meta and not self.read_only:
            try:
                unscoped = self.db.execute("SELECT 1 FROM events LIMIT 1").fetchone() is not None
                with self.db:
                    self.db.execute("INSERT OR IGNORE INTO meta VALUES ('capture_policy', ?)",
                                    ("legacy_unscoped_rows" if unscoped else "scoped",))
            except sqlite3.Error:
                pass
        self.counts_available = bool(self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='retrieval_counts'").fetchone())
        self.fts = bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='search'").fetchone())

    def close(self) -> None:
        self.db.close()

    def count_retrieval(self, outcome: str) -> None:
        """Count a completed CLI retrieval without storing keys or result content."""
        if outcome not in ("lookup_found", "lookup_ambiguous", "lookup_unverified",
                           "lookup_paged", "lookup_not_found", "search_hit", "search_miss",
                           "fetch_hit"):
            # An unfamiliar future status must not replace a successful retrieval with an error.
            return
        if self.read_only or not self.counts_available:
            return
        try:
            with self.db:
                self.db.execute("INSERT INTO retrieval_counts(outcome,count) VALUES (?,1) "
                                "ON CONFLICT(outcome) DO UPDATE SET count=count+1", (outcome,))
        except sqlite3.Error:
            # Measurement cannot block access to already captured evidence.
            pass

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

    def _read_batch(self, stream: Any, source: str, offset: int, *, cutoff: str,
                    scope: CaptureScope) -> dict[str, Any]:
        read_bytes = 0
        rows = 0
        rejected = 0
        counts = dict.fromkeys(CAPTURE_COUNTERS, 0)
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
                try:
                    events = tool_events(row)
                except ValueError as exc:
                    if str(exc) != "invalid_tool_identity":
                        raise
                    # Keep the cursor at this row so a repaired transcript can
                    # be retried without losing earlier committed evidence.
                    status = "invalid_tool_identity"
                    break
                if any(len(event["call_id"]) > 512 or len(event["name"]) > 256 for event in events):
                    status = "invalid_tool_identity"
                    break
                for event in events:
                    if event["kind"] == "call":
                        decision, _ = scope.classify(event)
                        if decision != "capture":
                            counts["calls_withheld_restricted" if decision == "withhold"
                                   else "calls_out_of_scope"] += 1
                            continue
                    else:
                        stored = self.db.execute(
                            "SELECT name, body FROM events WHERE call_id=? AND kind='call' AND source=? LIMIT 1",
                            (event["call_id"], source)).fetchone()
                        if not stored:
                            # A result is stored only beside its own stored call from this transcript.
                            counts["results_without_stored_call"] += 1
                            continue
                        # Recheck the call under the current scope: the configuration may have changed, or the
                        # call may come from a legacy unscoped index, since the call was stored.
                        if scope.classify({"name": stored["name"], "body": json.loads(stored["body"])})[0] != "capture":
                            counts["results_withheld_by_scope"] += 1
                            continue
                    self._insert_event(event, row, source, start)
            offset = stream.tell()
            rows += 1
        else:
            status = "more_pending"
        return {"status": status, "offset": offset, "bytes_read": read_bytes,
                "rows": rows, "rows_excluded_by_plan": rejected, **counts}

    def _capture_counts(self) -> dict[str, int]:
        row = self.db.execute("SELECT value FROM meta WHERE key='capture_counts'").fetchone()
        try:
            stored = json.loads(row[0]) if row else {}
        except (TypeError, ValueError):
            stored = {}
        stored = stored if isinstance(stored, dict) else {}
        return {key: stored[key] if type(stored.get(key)) is int else 0 for key in CAPTURE_COUNTERS}

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

    def sync(self, transcript: Path, *, cutoff: str = "", scope: CaptureScope | None = None) -> dict[str, Any]:
        """Incrementally ingest one explicitly scoped transcript; no directory scans."""
        scope = scope or CaptureScope()
        if transcript.is_symlink() or not transcript.is_file():
            raise ValueError("transcript_unavailable")
        source = sha(str(transcript.absolute()).encode())
        cursor = self.db.execute("SELECT * FROM cursors WHERE source=?", (source,)).fetchone()
        if cursor and (type(cursor["offset"]) is not int or cursor["offset"] < 0
                       or not isinstance(cursor["anchor"], str) or not re.fullmatch(r"[0-9a-f]{64}", cursor["anchor"])
                       or not isinstance(cursor["identity"], str) or not re.fullmatch(r"[0-9]+:[0-9]+:[0-9]+:-?[0-9]+", cursor["identity"])):
            raise ValueError("invalid_cursor")
        with transcript.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            identity = f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}"
            offset = cursor["offset"] if cursor else 0
            stream.seek(0)
            prefix = stream.read(min(offset, 4096))
            anchor_start = max(0, offset - 4096)
            stream.seek(anchor_start)
            anchor = sha(prefix + stream.read(offset - anchor_start))
            previous = cursor["identity"].split(":") if cursor else []
            changed_file = bool(previous and (previous[:2] != identity.split(":")[:2]
                                or (int(previous[2]) == stat.st_size and previous[3] != str(stat.st_mtime_ns))))
            reset = bool(cursor and (changed_file or stat.st_size < offset or cursor["anchor"] != anchor))
            identity_bytes = 0
            if not cursor or reset or stat.st_ino == 0:
                stream.seek(0)
                identity_bytes = self._verify_source(stream)
            if reset:
                offset = 0
            stream.seek(offset)
            with self.db:
                result = self._read_batch(stream, source, offset, cutoff=cutoff, scope=scope)
                offset = result["offset"]
                if any(result[key] for key in CAPTURE_COUNTERS):
                    totals = self._capture_counts()
                    self.db.execute("INSERT OR REPLACE INTO meta VALUES ('capture_counts', ?)",
                                    (encoded({key: totals[key] + result[key] for key in CAPTURE_COUNTERS}),))
                stream.seek(0)
                prefix = stream.read(min(offset, 4096))
                stream.seek(max(0, offset - 4096))
                anchor = sha(prefix + stream.read(min(offset, 4096)))
                self.db.execute("INSERT OR REPLACE INTO cursors VALUES (?, ?, ?, ?)",
                                (source, offset, anchor, identity))
                if result["rows"]:
                    self.db.execute("UPDATE meta SET value=? WHERE key='expires'",
                                    (str(time.time() + RETENTION_SECONDS),))
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('last_sync', ?)", (encoded(result),))
                self.db.execute("DELETE FROM meta WHERE key='transcript_waits'")
            return {**result, "cursor_reset": reset, "identity_bytes_read": identity_bytes, "anchor_bytes_read": 2 * min(cursor["offset"], 4096) if cursor else 0}

    def search(self, query: str, *, limit: int = 10, offset: int = 0,
               kind: str | None = None) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError("invalid_search")
        if kind not in (None, "call", "result"):
            raise ValueError("invalid_search")
        if type(offset) is not int or offset < 0 or offset > 1000000:
            raise ValueError("invalid_page")
        limit = max(1, min(limit, 20))
        tokens = re.findall(r"\w+", query, re.UNICODE)[:8]
        if not tokens:
            raise ValueError("invalid_search")
        if self.fts:
            expression = " AND ".join('"' + token + '"' for token in tokens)
            kind_clause = " AND e.kind=?" if kind else ""
            values = (expression, kind, limit + 1, offset) if kind else (expression, limit + 1, offset)
            rows = self.db.execute(
                "SELECT e.id, e.call_id, e.kind, e.name, e.timestamp, e.error, substr(e.body,1,240) preview "
                "FROM search JOIN events e ON e.rowid=search.rowid WHERE search MATCH ?"
                f"{kind_clause} ORDER BY e.rowid DESC LIMIT ? OFFSET ?", values).fetchall()
        else:
            clauses = " AND ".join("(name || ' ' || body) LIKE ? ESCAPE '\\'" for _ in tokens)
            patterns = ["%" + token.replace("_", "\\_") + "%" for token in tokens]
            kind_clause = "kind=? AND " if kind else ""
            values = (kind, *patterns, limit + 1, offset) if kind else (*patterns, limit + 1, offset)
            rows = self.db.execute(
                "SELECT id, call_id, kind, name, timestamp, error, substr(body,1,240) preview "
                f"FROM events WHERE {kind_clause}{clauses} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                values).fetchall()
        return {"matches": [dict(row) for row in rows[:limit]], "more": len(rows) > limit,
                "next": offset + limit if len(rows) > limit else None,
                "search_mode": "fts5" if self.fts else "literal_scan", "transcript_bytes_read": 0,
                "trust": "untrusted historical evidence; completeness and current validity unknown"}

    def resolve_id(self, identity: str) -> str:
        """Return the stored ID for a full ID or a unique prefix of at least 12 hex characters."""
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{12,64}", identity):
            raise ValueError("evidence_not_found")
        if len(identity) == 64:
            return identity
        # Hex IDs sort below "g", so this range is exactly the prefix and uses the primary key.
        rows = self.db.execute("SELECT id FROM events WHERE id >= ? AND id < ? ORDER BY id LIMIT 2",
                               (identity, identity + "g")).fetchall()
        if not rows:
            raise ValueError("evidence_not_found")
        if len(rows) > 1:
            raise ValueError("ambiguous_id")
        return rows[0]["id"]

    def short_id(self, identity: str) -> str:
        """The shortest listed prefix (12 characters unless that is ambiguous) for an ID."""
        prefix = identity[:12]
        count = self.db.execute("SELECT count(*) FROM events WHERE id >= ? AND id < ?",
                                (prefix, prefix + "g")).fetchone()[0]
        return prefix if count == 1 else identity

    def _external_candidates(self, batch: int) -> Iterator[sqlite3.Row]:
        """Results whose call may name an external tool, newest arrival first.

        Pages by rowid until exhausted, so filtered candidates never hide an older eligible result.
        Order is by result arrival, not call order: overlapping calls can return out of order.
        """
        before: list[int] = []
        while True:
            rows = self.db.execute(
                "SELECT r.rowid AS position, r.id, r.call_id, r.source, r.timestamp, r.error, "
                "length(r.body) AS characters, c.name, c.body AS call_body FROM events r JOIN events c "
                "ON c.call_id=r.call_id AND c.kind='call' AND c.source IS r.source WHERE r.kind='result' AND "
                "(c.name LIKE 'mcp\\_\\_%' ESCAPE '\\' OR c.name IN (?, ?) OR c.body LIKE '%mcp\\_\\_%' ESCAPE '\\' "
                f"OR c.body LIKE '%web\\_\\_run%' ESCAPE '\\'){' AND r.rowid<?' if before else ''} "
                "ORDER BY r.rowid DESC LIMIT ?", (*WEB_TOOLS, *before, batch)).fetchall()
            yield from rows
            if len(rows) < batch:
                return
            before = [rows[-1]["position"]]

    def recent_external(self, scope: CaptureScope, limit: int = RECENT_RESULTS) -> list[dict[str, Any]]:
        """Most recently arrived paired external results, as IDs and metadata only; no call or result content."""
        listing = scope.listing()
        items, seen = [], set()
        for result in self._external_candidates(5 * limit):
            if result["id"] in seen:
                continue
            seen.add(result["id"])
            decision, tools = listing.classify({"name": result["name"], "body": json.loads(result["call_body"])})
            if decision != "capture":
                continue
            pair = self.db.execute("SELECT sum(kind='call'), sum(kind='result') FROM events "
                                   "WHERE call_id=? AND source IS ?", (result["call_id"], result["source"])).fetchone()
            if tuple(pair) != (1, 1):
                continue
            items.append({"id": self.short_id(result["id"]),
                          "tools": tools[:3] + ([f"+{len(tools) - 3} more"] if len(tools) > 3 else []),
                          "at": result["timestamp"], "logged_characters": result["characters"],
                          "host_error": bool(result["error"])})
            if len(items) == limit:
                break
        return items

    def fetch(self, identity: str, *, start: int = 0, pointer: str = "") -> dict[str, Any]:
        identity = self.resolve_id(identity)
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
        logged = json.loads(body)
        error_flag = logged.get("is_error") if row["kind"] == "result" and isinstance(logged, dict) else None
        host_error = bool(row["error"]) or error_flag is True
        host_error_signal = ("not_applicable" if row["kind"] != "result" else
                             "error_reported" if host_error else
                             "error_flag_false" if error_flag is False else "error_flag_absent")
        links = self.db.execute("SELECT id, kind, error FROM events WHERE call_id=? ORDER BY rowid LIMIT 21",
                                (row["call_id"],)).fetchall()
        calls = sum(link["kind"] == "call" for link in links)
        results = sum(link["kind"] == "result" for link in links)
        pairing = "ambiguous" if calls > 1 or results > 1 or len(links) > 20 else (
            "paired" if calls == results == 1 else "missing_call" if not calls else "missing_result")
        return {"id": identity, "call_id": row["call_id"], "kind": row["kind"],
                "timestamp": row["timestamp"], "sha256": sha(body.encode()), "pairing": pairing,
                "links": [dict(link) for link in links[:20]], "host_error": host_error,
                "host_error_signal": host_error_signal,
                "completeness": "unknown; only logged data preserved", "freshness": "historical; reverify for current claims",
                "pointer": pointer, "start": start, "text": selected[start:start + PAGE_CHARACTERS],
                "next": start + PAGE_CHARACTERS if start + PAGE_CHARACTERS < len(selected) else None,
                "total_characters": len(selected), "transcript_bytes_read": 0}

    def lookup(self, key: str) -> dict[str, Any]:
        """Resolve one exact evidence key and its current correction in one call.

        Ambiguous, failed, missing, and paged evidence remain explicit; callers
        use search/fetch/state for those cases instead of guessing.
        """
        page = self.search(key, limit=2, kind="result")
        results = page["matches"]
        if page["more"] or len(results) != 1:
            return {"status": "ambiguous" if page["more"] or results else "not_found",
                    "matches": page["matches"], "more": page["more"],
                    "trust": page["trust"], "transcript_bytes_read": 0}
        result = self.fetch(results[0]["id"])
        calls = [item for item in result["links"] if item["kind"] == "call"]
        if result["pairing"] != "paired" or result["host_error"] or len(calls) != 1:
            return {"status": "unverified", "pairing": result["pairing"],
                    "host_error": result["host_error"], "host_error_signal": result["host_error_signal"],
                    "result_id": result["id"],
                    "transcript_bytes_read": 0}
        call = self.fetch(calls[0]["id"])
        if result["next"] is not None or call["next"] is not None:
            return {"status": "paged", "result_id": result["id"],
                    "call_id": call["id"], "result_next": result["next"],
                    "call_next": call["next"], "transcript_bytes_read": 0}
        row = self.db.execute(
            "SELECT revision,kind,text,evidence FROM states WHERE key=? ORDER BY revision DESC LIMIT 1",
            (key.strip(),)).fetchone()
        if row is not None and len(row["text"]) > 512:
            return {"status": "paged", "result_id": result["id"],
                    "call_id": call["id"], "state_revision": row["revision"],
                    "transcript_bytes_read": 0}
        state = None if row is None else {"revision": row["revision"], "kind": row["kind"],
                                          "text": row["text"],
                                          "evidence": json.loads(row["evidence"])}
        return {"status": "found", "result_id": result["id"], "call_id": call["id"],
                "historical_result": json.loads(result["text"]),
                "logged_call": json.loads(call["text"]), "current_state": state,
                "host_error_signal": result["host_error_signal"],
                "freshness": result["freshness"], "completeness": result["completeness"],
                "transcript_bytes_read": 0}

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
            resolved = []
            for identity in evidence:
                try:
                    identity = self.resolve_id(identity)
                except ValueError as exc:
                    if str(exc) != "evidence_not_found":
                        raise
                    raise ValueError("state_evidence_not_found") from None
                if not self.db.execute("SELECT 1 FROM events WHERE id=?", (identity,)).fetchone():
                    raise ValueError("state_evidence_not_found")
                resolved.append(identity)
            evidence = resolved
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
        meta = dict(self.db.execute("SELECT key,value FROM meta"))
        return {"events": self.db.execute("SELECT count(*) FROM events").fetchone()[0],
                "state_revisions": self.db.execute("SELECT count(*) FROM states").fetchone()[0],
                "retrieval_counts": (dict(self.db.execute("SELECT outcome,count FROM retrieval_counts"))
                                     if self.counts_available else {}),
                "last_sync": json.loads(meta.get("last_sync", "null")),
                "capture_policy": meta.get("capture_policy", "unknown"),
                "capture_counts": self._capture_counts(),
                "database_bytes": self.path.stat().st_size, "quota_bytes": MAX_DATABASE_BYTES,
                "search_mode": "fts5" if self.fts else "literal_scan", "scope": "current session and plan",
                "read_only": self.read_only,
                "expires_at_unix": float(self.db.execute("SELECT value FROM meta WHERE key='expires'").fetchone()[0])}
