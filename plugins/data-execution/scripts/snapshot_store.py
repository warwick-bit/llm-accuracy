"""Private, content-addressed POSIX snapshots. No background deletion or network."""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from contextlib import contextmanager

from data_contract import DEFAULT_RETENTION_DAYS, MAX_INPUT, encode, parse_json, require

MAX_ENVELOPE = MAX_INPUT * 2
MAX_STORE = 256 * 1024 * 1024


def private_root(path):
    require(os.name == 'posix', 'unsupported_platform')
    path = Path(os.path.abspath(path))
    for ancestor in reversed((path,) + tuple(path.parents)):
        require(not ancestor.is_symlink(), 'symlink_path')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
            'unsafe_store_permissions')
    return path


def private_read(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600, 'unsafe_file_permissions')
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'stored_size_limit')
        return raw


@contextmanager
def locked(path):
    import fcntl
    root = private_root(path)
    fd = os.open(root / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600, 'unsafe_lock')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield root
    finally:
        os.close(fd)


def snapshot_path(root, identity):
    require(re.fullmatch('[a-f0-9]{64}', identity) is not None, 'invalid_snapshot_id')
    return root / (identity + '.json')


def envelope(root, identity):
    raw = private_read(snapshot_path(root, identity), MAX_ENVELOPE)
    require(hashlib.sha256(raw).hexdigest() == identity, 'snapshot_changed')
    result = parse_json(raw)
    require(isinstance(result, dict) and result.get('version') == 1, 'invalid_snapshot')
    return result


def purge_locked(root, now):
    removed = 0
    for path in root.glob('*.json'):
        # Unknown/corrupt files are never silently removed by retention cleanup.
        item = envelope(root, path.stem)
        if item['expires_at'] <= now:
            path.unlink()
            removed += 1
    return removed


def save(path, raw, config, retention_days=DEFAULT_RETENTION_DAYS, now=None):
    require(type(retention_days) is int and 1 <= retention_days <= 3650, 'invalid_retention')
    current = int(time.time()) if now is None else now
    body = {'version': 1, 'captured_at': current,
            'expires_at': current + retention_days * 86400,
            'adapter': config, 'raw_base64': base64.b64encode(raw).decode('ascii')}
    packed = encode(body)
    require(len(packed) <= MAX_ENVELOPE, 'stored_size_limit')
    identity = hashlib.sha256(packed).hexdigest()
    with locked(path) as root:
        purge_locked(root, current)
        destination = snapshot_path(root, identity)
        if destination.exists():
            envelope(root, identity)
            return identity, body
        used = sum(p.lstat().st_size for p in root.iterdir())
        require(used + len(packed) <= MAX_STORE, 'store_quota')
        fd, temporary = tempfile.mkstemp(prefix='.capture-', dir=root)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(packed)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, destination)
        finally:
            os.unlink(temporary)
    return identity, body


def load(path, identity, scope, now=None):
    current = int(time.time()) if now is None else now
    with locked(path) as root:
        body = envelope(root, identity)
        require(body['expires_at'] > current, 'snapshot_expired')
        require(body['adapter']['scope'] == scope, 'scope_mismatch')
        raw = base64.b64decode(body['raw_base64'], validate=True)
    return body, raw


def purge(path, now=None):
    with locked(path) as root:
        return purge_locked(root, int(time.time()) if now is None else now)


def delete(path, identity):
    with locked(path) as root:
        # Permit explicit deletion of a corrupt snapshot, without reading it.
        target = snapshot_path(root, identity)
        require(not target.is_symlink(), 'symlink_path')
        target.unlink()
