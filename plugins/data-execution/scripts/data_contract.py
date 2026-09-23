"""Explicit local adapters; never infer financial definitions from field names."""
from __future__ import annotations

import csv
import io
import json
import re
from decimal import Decimal, Inexact, localcontext

MAX_INPUT = 16 * 1024 * 1024
MAX_OUTPUT = 16 * 1024
MAX_ROWS = 100000
DEFAULT_RETENTION_DAYS = 30


class DataError(Exception):
    """A public error code with no input content."""


def require(condition, code):
    if not condition:
        raise DataError(code)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def invalid_constant(_value):
    raise DataError('nonfinite_json')


def parse_json(raw):
    return json.loads(raw, parse_float=Decimal, object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'),
                      sort_keys=True, allow_nan=False).encode('utf-8')


def at_path(value, path):
    for key in path:
        require(isinstance(value, dict) and key in value, 'missing_path')
        value = value[key]
    return value


def short_text(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def adapter(config):
    require(isinstance(config, dict), 'invalid_adapter')
    required = {'format', 'records_path', 'id_field', 'amount_field', 'group_field',
                'unit', 'scope', 'complete', 'atomic_snapshot', 'caveats'}
    require(set(config) == required, 'invalid_adapter_fields')
    require(config['format'] in ('json', 'csv'), 'unsupported_format')
    path = config['records_path']
    require(isinstance(path, list) and len(path) <= 8 and all(map(short_text, path)),
            'invalid_records_path')
    for key in ('id_field', 'amount_field', 'group_field', 'unit', 'scope'):
        require(short_text(config[key]), 'invalid_adapter_text')
    require(len({config[k] for k in ('id_field', 'amount_field', 'group_field')}) == 3,
            'overlapping_fields')
    require(type(config['atomic_snapshot']) is bool, 'invalid_atomic_snapshot')
    require(isinstance(config['caveats'], list) and len(config['caveats']) <= 8
            and all(map(short_text, config['caveats'])), 'invalid_caveats')
    complete = config['complete']
    require(isinstance(complete, dict) and len(complete) == 1, 'invalid_completeness')
    if 'path' in complete:
        require(config['format'] == 'json' and isinstance(complete['path'], list)
                and 0 < len(complete['path']) <= 8
                and all(map(short_text, complete['path'])), 'invalid_completeness_path')
    else:
        require(set(complete) == {'asserted'} and type(complete['asserted']) is bool,
                'invalid_completeness_assertion')
    require(config['format'] != 'csv' or not path, 'csv_records_path')
    return config


def decimal_amount(value):
    require(type(value) in (str, int, Decimal), 'invalid_amount_type')
    text = str(value)
    require(re.fullmatch(r'-?\d{1,80}(?:\.\d{1,30})?', text) is not None,
            'invalid_amount')
    return Decimal(text)


def csv_rows(raw):
    reader = csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True)
    header = next(reader, None)
    require(header and all(header) and len(set(header)) == len(header), 'invalid_csv_header')
    rows = []
    for row in reader:
        require(len(row) == len(header), 'invalid_csv_width')
        rows.append(dict(zip(header, row)))
        require(len(rows) <= MAX_ROWS, 'row_limit')
    return rows


def records(raw, config):
    adapter(config)
    require(len(raw) <= MAX_INPUT, 'input_limit')
    if config['format'] == 'json':
        body = parse_json(raw)
        rows = at_path(body, config['records_path'])
    else:
        body, rows = None, csv_rows(raw)
    complete = config['complete']
    completeness = (at_path(body, complete['path']) if 'path' in complete
                    else complete['asserted'])
    require(type(completeness) is bool, 'invalid_completeness_value')
    require(isinstance(rows, list) and len(rows) <= MAX_ROWS, 'invalid_records')
    seen = set()
    for row in rows:
        require(isinstance(row, dict), 'invalid_record')
        require(all(key in row for key in
                    (config['id_field'], config['amount_field'], config['group_field'])),
                'missing_field')
        identity, group = row[config['id_field']], row[config['group_field']]
        require(short_text(identity) and short_text(group), 'invalid_identity_or_group')
        require(identity not in seen, 'duplicate_record_id')
        seen.add(identity)
        decimal_amount(row[config['amount_field']])
    return rows, completeness


def aggregate(rows, config, complete):
    require(complete, 'incomplete_source')
    totals = {}
    with localcontext() as ctx:
        ctx.prec = 128
        ctx.traps[Inexact] = True
        for row in rows:
            group = row[config['group_field']]
            totals[group] = totals.get(group, Decimal(0)) + decimal_amount(row[config['amount_field']])
    return [{'group': key, 'sum': format(value, 'f')} for key, value in sorted(totals.items())]


def wire(value):
    """Protect source numbers before JSON/JavaScript transport, including detail."""
    if type(value) in (int, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [wire(item) for item in value]
    return value
