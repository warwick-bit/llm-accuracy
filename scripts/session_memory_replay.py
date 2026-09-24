#!/usr/bin/env python3
"""Paired synthetic long-session retrieval experiment; aggregate JSON only."""
from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / 'plugins/session-ledger/hooks'
CASES = 12
COMPACTIONS = 3


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HOOKS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CountedReader:
    def __init__(self, stream: Any, counter: dict[str, int]):
        self.stream = stream
        self.counter = counter

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> None:
        self.stream.close()

    def read(self, *args: Any) -> bytes:
        value = self.stream.read(*args)
        self.counter['bytes'] += len(value)
        return value

    def readline(self, *args: Any) -> bytes:
        value = self.stream.readline(*args)
        self.counter['bytes'] += len(value)
        return value


@contextmanager
def observe_reads(path: Path, counter: dict[str, int]) -> Iterator[None]:
    """Count logical bytes and attempted opens through Python file APIs."""
    original = builtins.open

    def observed(file: Any, *args: Any, **kwargs: Any) -> Any:
        matches = isinstance(file, (str, Path)) and Path(file).absolute() == path.absolute()
        if matches:
            counter['opens'] += 1
        stream = original(file, *args, **kwargs)
        return CountedReader(stream, counter) if matches else stream

    # Python 3.10 pathlib caches its opener; intercept Path.open directly too.
    with patch('builtins.open', observed), patch('io.open', observed), patch.object(Path, 'open', observed):
        yield


def write(stream: Any, row: dict[str, Any]) -> None:
    stream.write(json.dumps(row, ensure_ascii=False).encode('utf-8') + b'\n')


def tool_row(block: dict[str, Any], role: str = 'assistant') -> dict[str, Any]:
    return {'sessionId': 'synthetic-replay', 'timestamp': '2026-09-01T00:00:00Z',
            'message': {'role': role, 'content': [block]}}


def seed(transcript: Path) -> dict[str, Any]:
    expected = {}
    with transcript.open('wb') as stream:
        for index in range(CASES):
            key = f'syntheticmetric{index}'
            block = {'type': 'tool_result', 'tool_use_id': f'call-{index}',
                     'content': {'metric': key, 'value': 100 + index, 'currency': 'AUD',
                                 'filters': {'status': 'collected'}, 'note': '❯ → ●'}}
            expected[key] = block
            write(stream, tool_row({'type': 'tool_use', 'id': f'call-{index}',
                  'name': 'query_dataset', 'input': {'metric': key, 'status': 'collected'}}))
            write(stream, tool_row(block, 'user'))
            write(stream, {'message': {'role': 'assistant', 'content':
                  f"Earlier evidence {key}: {100 + index} collected AUD."}})
    return expected


def compact_work(transcript: Path, store: Any, ledger: Any, root: Path,
                 counter: dict[str, int]) -> dict[str, Any]:
    payload = {'session_id': 'synthetic-replay', 'cwd': str(root), 'transcript_path': str(transcript)}
    ledger.update_ledger(payload, data_root=root)
    for phase in range(COMPACTIONS):
        with transcript.open('ab') as stream:
            for index in range(80):
                filler = ' '.join(hashlib.sha256(f'{phase}/{index}/{part}'.encode()).hexdigest() for part in range(55))
                write(stream, {'message': {'role': 'assistant', 'content':
                      f'Unrelated synthetic work phase {phase} row {index}: ' + filler}})
        ledger.update_ledger(payload, data_root=root)
        ledger.write_compact_summary({**payload, 'compact_summary': f'Completed unrelated phase {phase}.'}, data_root=root)
        ledger.session_start_context({**payload, 'source': 'compact'}, data_root=root)
        with observe_reads(transcript, counter):
            while True:
                batch = store.sync(transcript)
                if batch['status'] == 'caught_up':
                    break
                if batch['status'] != 'more_pending':
                    raise AssertionError(batch['status'])
    return ledger.load_current_record(payload, data_root=root, now=ledger.utc_now())


def scan_oracles(transcript: Path, engine: Any, expected: dict[str, Any]) -> dict[str, Any]:
    def blocks() -> list[Any]:
        return [event['body'] for line in transcript.read_bytes().splitlines()
                for event in engine.tool_events(json.loads(line))]

    repeated = {'bytes': 0, 'opens': 0}
    batched = {'bytes': 0, 'opens': 0}
    with observe_reads(transcript, repeated):
        individual_recovery = sum(block in blocks() for block in expected.values())
    with observe_reads(transcript, batched):
        all_blocks = blocks()
        batched_recovery = sum(block in all_blocks for block in expected.values())
    return {'repeated_full_scan_transcript_bytes': repeated['bytes'],
            'batched_full_scan_transcript_bytes': batched['bytes'],
            'full_log_scan_exact_recovery_before_deletion': individual_recovery,
            'batched_scan_exact_recovery_before_deletion': batched_recovery}


def run() -> dict[str, Any]:
    engine, ledger = load('session_memory'), load('session-ledger')
    with tempfile.TemporaryDirectory(prefix='session-memory-replay-') as directory:
        root = Path(directory)
        transcript = root / 'session.jsonl'
        expected = seed(transcript)
        store = engine.Store(root / 'memory.sqlite3', 'synthetic-replay', 'default', create=True)
        indexed = {'bytes': 0, 'opens': 0}
        with observe_reads(transcript, indexed):
            store.sync(transcript)
        for key in expected:
            evidence = [item['id'] for item in store.search(key)['matches'] if item['kind'] == 'result']
            revision = store.remember(key, 'definition', 'Use gross AUD.', evidence)
            store.remember(key, 'correction', 'Use collected AUD before fees.', evidence, revision)
        record = compact_work(transcript, store, ledger, root, indexed)
        scans = scan_oracles(transcript, engine, expected)
        rolling = sum(key in json.dumps(record) for key in expected)
        transcript.unlink()
        queries = {'bytes': 0, 'opens': 0}
        recovered = 0
        started = time.perf_counter()
        with observe_reads(transcript, queries):
            for key, block in expected.items():
                hits = [item for item in store.search(key)['matches'] if item['kind'] == 'result']
                recovered += len(hits) == 1 and json.loads(store.fetch(hits[0]['id'])['text']) == block
        elapsed = time.perf_counter() - started
        corrections = sum(item['text'] == 'Use collected AUD before fees.' for item in store.state(limit=20)['items'])
        storage = store.status()['database_bytes']
        store.close()
        passed = (recovered == corrections == CASES and queries['opens'] == 0
                  and 0 < indexed['bytes'] < 2 * scans['batched_full_scan_transcript_bytes']) and all(
            scans[key] == CASES for key in ('full_log_scan_exact_recovery_before_deletion', 'batched_scan_exact_recovery_before_deletion'))
        return {'passed': passed, 'population': 'synthetic retrieval requests; no model answers scored',
                'cases': CASES, 'compactions': COMPACTIONS, 'indexed_exact_recovery_after_log_deletion': recovered,
                **scans, 'rolling_ledger_early_identifiers_retained': rolling,
                'current_corrections_recovered': corrections, 'index_ingestion_transcript_bytes': indexed['bytes'],
                'indexed_lookup_transcript_bytes': queries['bytes'], 'indexed_lookup_transcript_opens': queries['opens'],
                'database_bytes': storage, 'indexed_lookup_elapsed_seconds': round(elapsed, 4),
                'limits': 'Logical Python file reads, not physical disk I/O. Batched scan may cost less initially. No real-session frequency or model accuracy uplift measured.'}


if __name__ == '__main__':
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
