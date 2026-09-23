#!/usr/bin/env python3
"""Synthetic CLI usefulness experiment. Reports metadata only, never source rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'plugins/data-execution/scripts/local_data.py'


def invoke(root, *args):
    result = subprocess.run([sys.executable, str(CLI), '--store', str(root / 'store'), *args],
                            capture_output=True, timeout=20, check=True)
    assert not result.stderr
    return json.loads(result.stdout), len(result.stdout)


def run_case(count, detail_count):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = {'format': 'json', 'records_path': ['records'], 'id_field': 'id',
                  'amount_field': 'amount', 'group_field': 'currency', 'unit': 'minor units',
                  'scope': 'fictional:test:period-A:transaction:v1',
                  'complete': {'path': ['complete']}, 'atomic_snapshot': False,
                  'caveats': ['Complete export is not an atomic source snapshot.']}
        rows = [{'id': f'item-{i}', 'amount': str(9007199254740993 + i),
                 'currency': 'AAA' if i % 2 else 'BBB',
                 'description': 'synthetic detail ' + 'q' * 240} for i in range(count)]
        raw = json.dumps({'complete': True, 'records': rows}, separators=(',', ':')).encode()
        source, adapter = root / 'export.json', root / 'adapter.json'
        source.write_bytes(raw)
        adapter.write_text(json.dumps(config))
        rec, capture_bytes = invoke(root, 'capture', '--adapter', str(adapter), '--input', str(source))
        source.unlink()  # Every subsequent query is a fresh process without the original export.
        totals, sum_bytes = invoke(root, 'sum', rec['snapshot'], '--scope', config['scope'])
        expected = {}
        for row in rows:
            expected[row['currency']] = expected.get(row['currency'], 0) + int(row['amount'])
        assert totals['totals'] == [{'group': k, 'sum': str(v)} for k, v in sorted(expected.items())]
        detail_bytes = 0
        returned = []
        # Entire selected rows, split into packets under the output cap.
        for start in range(0, detail_count, 20):
            args = ['detail', rec['snapshot'], '--scope', config['scope']]
            for row in rows[start:min(start + 20, detail_count)]:
                args += ['--id', row['id']]
            for field in ['amount', 'currency', 'description']:
                args += ['--field', field]
            detail, size = invoke(root, *args)
            returned.extend(detail['detail'])
            detail_bytes += size
        assert returned == rows[:detail_count]
        packed = (root / 'store' / (rec['snapshot'] + '.json')).read_bytes()
        assert hashlib.sha256(packed).hexdigest() == rec['snapshot']
        # Conservative baseline: source enters context once; no repeated raw reads charged.
        compact = capture_bytes + sum_bytes + detail_bytes
        return {'rows': count, 'detail_rows': detail_count, 'raw_output_bytes': len(raw) + 1,
                'capture_output_bytes': capture_bytes, 'sum_output_bytes': sum_bytes,
                'already_captured_control_output_bytes': sum_bytes + detail_bytes,
                'detail_output_bytes': detail_bytes, 'total_compact_output_bytes': compact,
                'output_byte_reduction_percent': round(100 * (1 - compact / (len(raw) + 1)), 1),
                'exact_totals': True, 'exact_details': True, 'source_deleted_before_followup': True,
                'snapshot_bytes_on_disk': len(packed)}


def experiment():
    if os.name != 'posix':
        raise SystemExit('POSIX-only pilot')
    return {'population': 'new synthetic JSON exports; no provider data',
            'unit': 'UTF-8 tool-result bytes including newline; not tokens',
            'baseline': 'one full raw response; followups reuse data already in context',
            'candidate': 'capture receipt + grouped sum receipt + selected full-row detail packets',
            'control': 'same queries against an existing snapshot; excludes capture receipt; not a native Claude spill benchmark',
            'exclusions': ['model input/output tokens', 'tool call arguments', 'installation/skill context',
                           'provider request costs', 'model reasoning accuracy', 'live source correctness'],
            'cases': [run_case(1, 1), run_case(1000, 1), run_case(1000, 1000)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = json.dumps(experiment(), indent=2) + '\n'
    if args.output:
        args.output.write_text(report)
    else:
        print(report, end='')
