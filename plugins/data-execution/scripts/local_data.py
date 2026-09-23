#!/usr/bin/env python3
"""Capture directly from a trusted producer; emit bounded receipts, never raw capture."""
from __future__ import annotations

import argparse
import csv
from decimal import DecimalException
import os
from pathlib import Path

from data_contract import (DEFAULT_RETENTION_DAYS, DataError, MAX_INPUT, MAX_OUTPUT,
                           adapter, aggregate, encode, parse_json, records, require, wire)
import snapshot_store as store


def receipt(identity, body, rows, complete):
    config = body['adapter']
    return {'snapshot': identity, 'scope': config['scope'], 'rows': len(rows),
            'captured_at': body['captured_at'], 'expires_at': body['expires_at'],
            'complete': complete, 'totals_status': 'available' if complete else 'withheld',
            'completeness_basis': config['complete'],
            'atomic_snapshot': config['atomic_snapshot'], 'unit': config['unit'],
            'caveats': config['caveats']}


def read_input(path):
    require(path != '-', 'staged_file_required')
    with open(path, 'rb') as stream:
        result = stream.read(MAX_INPUT + 1)
    require(len(result) <= MAX_INPUT, 'input_limit')
    return result


def default_store():
    data = os.environ.get('CLAUDE_PLUGIN_DATA')
    return str(Path(data) / 'snapshots' if data else
               Path.home() / '.local/share/llm-accuracy/data-execution')


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--store', default=default_store())
    sub = result.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--adapter', required=True)
    capture.add_argument('--input', required=True)
    capture.add_argument('--retention-days', type=int, default=DEFAULT_RETENTION_DAYS)
    for name in ('sum', 'detail'):
        command = sub.add_parser(name)
        command.add_argument('snapshot')
        command.add_argument('--scope', required=True)
        if name == 'detail':
            command.add_argument('--id', action='append', required=True)
            command.add_argument('--field', action='append', required=True)
    sub.add_parser('purge')
    deletion = sub.add_parser('delete')
    deletion.add_argument('snapshot')
    return result


def capture(args):
    config = adapter(parse_json(read_input(args.adapter)))
    raw = read_input(args.input)
    rows, complete = records(raw, config)
    identity, body = store.save(args.store, raw, config, args.retention_days)
    return receipt(identity, body, rows, complete)


def query(args):
    body, raw = store.load(args.store, args.snapshot, args.scope)
    config = body['adapter']
    rows, complete = records(raw, config)
    result = receipt(args.snapshot, body, rows, complete)
    if args.command == 'sum':
        result['totals'] = aggregate(rows, config, complete)
        result['group_field'] = config['group_field']
        result['amount_field'] = config['amount_field']
    else:
        require(len(args.id) <= 100 and len(args.field) <= 20, 'detail_limit')
        require(len(set(args.id)) == len(args.id), 'duplicate_requested_id')
        selected = {row[config['id_field']]: row for row in rows if row[config['id_field']] in args.id}
        require(len(selected) == len(args.id), 'record_missing')
        require(all(field in row for row in selected.values() for field in args.field),
                'field_missing')
        fields = list(dict.fromkeys([config['id_field']] + args.field))
        result['detail'] = wire([{field: selected[key][field] for field in fields} for key in args.id])
        result['numbers_encoded_as_strings'] = True
    return result


def run(args):
    if args.command == 'capture':
        return capture(args)
    if args.command == 'purge':
        return {'deleted_expired': store.purge(args.store)}
    if args.command == 'delete':
        store.delete(args.store, args.snapshot)
        return {'deleted': True}
    return query(args)


def main():
    args = parser().parse_args()
    try:
        output = encode(run(args))
        require(len(output) + 1 <= MAX_OUTPUT, 'output_limit')
        print(output.decode('utf-8'))
        return 0
    except DataError as error:
        code = str(error)
    except FileNotFoundError:
        code = 'file_missing'
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError,
            OSError, csv.Error, DecimalException):
        code = 'invalid_or_unavailable_data'
    print(encode({'error': code}).decode('utf-8'))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
