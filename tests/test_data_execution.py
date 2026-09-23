"""Synthetic lifecycle and fidelity tests; no provider or model credentials."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/data-execution/scripts'
sys.path.insert(0, str(SCRIPTS))
import data_contract as contract  # noqa: E402
import snapshot_store as store  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='POSIX pilot')


def config(fmt='json'):
    return {'format': fmt, 'records_path': ['records'] if fmt == 'json' else [],
            'id_field': 'id', 'amount_field': 'amount', 'group_field': 'currency',
            'unit': 'minor currency units', 'scope': 'demo:test:all:period-A:transaction',
            'complete': {'path': ['complete']} if fmt == 'json' else {'asserted': True},
            'atomic_snapshot': False, 'caveats': ['Pagination is not an atomic snapshot.']}


def raw_data(count=2, complete=True):
    return json.dumps({'complete': complete, 'records': [
        {'id': 'row-' + str(i), 'amount': '9007199254740993.01',
         'currency': 'USD' if i % 2 else 'AUD', 'note': 'private detail ' + 'x' * 100,
         'integer': 9007199254740993} for i in range(count)]}).encode()


def cli(tmp_path, *args):
    proc = subprocess.run([sys.executable, str(SCRIPTS / 'local_data.py'),
                           '--store', str(tmp_path / 'store'), *map(str, args)],
                          capture_output=True, timeout=10)
    assert not proc.stderr, proc.stderr.decode()
    return proc.returncode, json.loads(proc.stdout)


def capture(tmp_path, raw=None, conf=None, *extra):
    source = tmp_path / 'source.json'
    source.write_bytes(raw if raw is not None else raw_data())
    mapping = tmp_path / 'adapter.json'
    mapping.write_text(json.dumps(conf or config()))
    return cli(tmp_path, 'capture', '--adapter', mapping, '--input', source, *extra)


def test_fresh_process_followup_preserves_exact_source_after_original_deleted(tmp_path):
    original = raw_data()
    code, receipt = capture(tmp_path, original)
    assert code == 0
    assert receipt['expires_at'] - receipt['captured_at'] == 30 * 86400
    assert 'private detail' not in json.dumps(receipt)
    (tmp_path / 'source.json').unlink()
    code, sums = cli(tmp_path, 'sum', receipt['snapshot'], '--scope', config()['scope'])
    assert code == 0
    assert sums['totals'] == [{'group': 'AUD', 'sum': '9007199254740993.01'},
                              {'group': 'USD', 'sum': '9007199254740993.01'}]
    code, detail = cli(tmp_path, 'detail', receipt['snapshot'], '--scope', config()['scope'],
                       '--id', 'row-1', '--field', 'integer', '--field', 'note')
    assert code == 0
    assert detail['detail'][0]['integer'] == '9007199254740993'
    assert detail['detail'][0]['note'] == json.loads(original)['records'][1]['note']
    _, preserved = store.load(tmp_path / 'store', receipt['snapshot'], config()['scope'])
    assert preserved == original


def test_csv_adapter_exact_decimal_and_no_currency_mixing(tmp_path):
    raw = b'id,amount,currency,description\na,0.10,AUD,"line one\nline two"\nb,0.20,AUD,x\nc,-0.01,USD,y\n'
    code, receipt = capture(tmp_path, raw, config('csv'))
    assert code == 0
    code, result = cli(tmp_path, 'sum', receipt['snapshot'], '--scope', config()['scope'])
    assert code == 0
    assert result['totals'] == [{'group': 'AUD', 'sum': '0.30'}, {'group': 'USD', 'sum': '-0.01'}]


def test_custom_nested_json_mapping(tmp_path):
    conf = config()
    conf.update(records_path=['structuredContent', 'items'], id_field='key',
                amount_field='value', group_field='bucket', unit='count')
    conf['complete'] = {'path': ['structuredContent', 'exhausted']}
    raw = b'{"structuredContent":{"items":[{"key":"a","value":"7","bucket":"team"}],"exhausted":true}}'
    code, rec = capture(tmp_path, raw, conf)
    assert code == 0
    code, result = cli(tmp_path, 'sum', rec['snapshot'], '--scope', conf['scope'])
    assert code == 0 and result['totals'] == [{'group': 'team', 'sum': '7'}]


def test_partial_detail_preserves_warning_and_sum_is_withheld(tmp_path):
    code, rec = capture(tmp_path, raw_data(complete=False))
    assert code == 0 and rec['totals_status'] == 'withheld'
    code, result = cli(tmp_path, 'sum', rec['snapshot'], '--scope', config()['scope'])
    assert code == 1 and result == {'error': 'incomplete_source'}
    code, result = cli(tmp_path, 'detail', rec['snapshot'], '--scope', config()['scope'],
                       '--id', 'row-0', '--field', 'amount')
    assert code == 0 and result['complete'] is False and result['totals_status'] == 'withheld'


@pytest.mark.parametrize('days', [1, 30, 90, 3650])
def test_retention_custom_boundary_and_cleanup(tmp_path, days):
    identity, body = store.save(tmp_path / 'store', raw_data(), config(), days, now=100)
    assert body['expires_at'] == 100 + days * 86400
    store.load(tmp_path / 'store', identity, config()['scope'], now=body['expires_at'] - 1)
    with pytest.raises(contract.DataError, match='snapshot_expired'):
        store.load(tmp_path / 'store', identity, config()['scope'], now=body['expires_at'])
    assert (tmp_path / 'store' / (identity + '.json')).exists()
    assert store.purge(tmp_path / 'store', now=body['expires_at']) == 1
    assert not (tmp_path / 'store' / (identity + '.json')).exists()


@pytest.mark.parametrize('days', [0, -1, 3651, True, 1.5])
def test_bad_retention_rejected_without_capture(tmp_path, days):
    with pytest.raises(contract.DataError, match='invalid_retention'):
        store.save(tmp_path / 'store', raw_data(), config(), days)
    assert not (tmp_path / 'store').exists()


def test_capture_purges_expired_and_delete_is_explicit(tmp_path):
    old, _ = store.save(tmp_path / 'store', raw_data(), config(), 1, now=1)
    new, _ = store.save(tmp_path / 'store', raw_data(), config(), now=86401)
    assert not (tmp_path / 'store' / (old + '.json')).exists()
    store.delete(tmp_path / 'store', new)
    with pytest.raises(FileNotFoundError):
        store.load(tmp_path / 'store', new, config()['scope'])


def test_identity_hash_covers_source_and_all_metadata(tmp_path):
    identity, _ = store.save(tmp_path / 'store', raw_data(), config(), now=100)
    path = tmp_path / 'store' / (identity + '.json')
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == identity
    for field in ['scope', 'complete', 'caveats']:
        body = json.loads(original)
        body['adapter'][field] = 'changed'
        path.write_text(json.dumps(body))
        with pytest.raises(contract.DataError, match='snapshot_changed'):
            store.load(tmp_path / 'store', identity, config()['scope'], now=101)
    path.write_bytes(original)
    with pytest.raises(contract.DataError, match='scope_mismatch'):
        store.load(tmp_path / 'store', identity, 'other-account', now=101)


def test_permission_symlink_and_traversal_guards(tmp_path):
    root = tmp_path / 'store'
    identity, _ = store.save(root, raw_data(), config())
    assert root.stat().st_mode & 0o777 == 0o700
    target = root / (identity + '.json')
    assert target.stat().st_mode & 0o777 == 0o600
    target.chmod(0o644)
    with pytest.raises(contract.DataError, match='unsafe_file_permissions'):
        store.load(root, identity, config()['scope'])
    target.chmod(0o600)
    link = tmp_path / 'link'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(contract.DataError, match='symlink_path'):
        store.load(link / 'child', identity, config()['scope'])
    with pytest.raises(contract.DataError, match='invalid_snapshot_id'):
        store.load(root, '../source', config()['scope'])
    target.unlink()
    source = tmp_path / 'source'
    source.write_text('sensitive')
    target.symlink_to(source)
    code, result = cli(tmp_path, 'sum', identity, '--scope', config()['scope'])
    assert code == 1 and 'sensitive' not in json.dumps(result)


@pytest.mark.parametrize('raw,error', [
    (b'{"complete":true,"complete":false,"records":[]}', 'duplicate_json_key'),
    (b'{"complete":true,"records":NaN}', 'nonfinite_json'),
    (b'{"complete":"true","records":[]}', 'invalid_completeness_value'),
    (b'{"complete":true,"records":[{}]}', 'missing_field'),
    (b'{"complete":true,"records":[]', 'invalid_or_unavailable_data'),
])
def test_invalid_sources_never_persist(tmp_path, raw, error):
    code, result = capture(tmp_path, raw)
    assert code == 1 and result['error'] == error
    assert not (tmp_path / 'store').exists()


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '1e90', 'x', None, True, '0.' + '1' * 31])
def test_invalid_amounts(tmp_path, value):
    body = json.loads(raw_data())
    body['records'][0]['amount'] = value
    code, _ = capture(tmp_path, json.dumps(body).encode())
    assert code == 1 and not (tmp_path / 'store').exists()


def test_duplicate_ids_missing_detail_and_output_bound(tmp_path):
    body = json.loads(raw_data())
    body['records'][1]['id'] = body['records'][0]['id']
    code, error = capture(tmp_path, json.dumps(body).encode())
    assert code == 1 and error['error'] == 'duplicate_record_id'
    body['records'][1]['id'] = 'row-1'
    body['records'][0]['note'] = 'sensitive' * 3000
    code, rec = capture(tmp_path, json.dumps(body).encode())
    assert code == 0
    for identity, field, expected in [('unknown', 'amount', 'record_missing'),
                                       ('row-0', 'unknown', 'field_missing'),
                                       ('row-0', 'note', 'output_limit')]:
        code, result = cli(tmp_path, 'detail', rec['snapshot'], '--scope', config()['scope'],
                           '--id', identity, '--field', field)
        assert code == 1 and result == {'error': expected}


def test_input_and_storage_quotas(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'MAX_STORE', 1)
    with pytest.raises(contract.DataError, match='store_quota'):
        store.save(tmp_path / 'store', raw_data(), config())
    assert not list((tmp_path / 'store').glob('*.json'))
    with pytest.raises(contract.DataError, match='input_limit'):
        contract.records(b' ' * (contract.MAX_INPUT + 1), config())


def test_exact_accumulation_beyond_decimal_default_precision():
    conf = config()
    raw = json.dumps({'complete': True, 'records': [
        {'id': str(i), 'amount': '9' * 80 + '.' + '9' * 30, 'currency': 'AAA'}
        for i in range(1000)]}).encode()
    rows, complete = contract.records(raw, conf)
    total = contract.aggregate(rows, conf, complete)[0]['sum']
    expected_units = int('9' * 110) * 1000
    whole, fraction = divmod(expected_units, 10**30)
    assert total == str(whole) + '.' + str(fraction).zfill(30)


def test_raw_bytes_not_normalized_and_capture_is_repeatable(tmp_path):
    raw = b' { "complete": true, "records": [] } \n'
    identity, _ = store.save(tmp_path / 'store', raw, config(), now=100)
    other, _ = store.save(tmp_path / 'store', raw, config(), now=100)
    assert other == identity
    body, recovered = store.load(tmp_path / 'store', identity, config()['scope'], now=101)
    assert base64.b64decode(body['raw_base64']) == recovered == raw


def test_no_hooks_or_execution_capability_and_distribution_boundary():
    plugin = ROOT / 'plugins/data-execution'
    assert not (plugin / 'hooks').exists()
    spec = importlib.util.spec_from_file_location('boundary', ROOT / 'scripts/check_distribution_boundary.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.boundary_violations(plugin, profile='data-execution') == []


def test_concurrent_captures_are_complete_and_readable(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(raw_data(50))
    mapping = tmp_path / 'adapter.json'
    mapping.write_text(json.dumps(config()))
    argv = [sys.executable, str(SCRIPTS / 'local_data.py'), '--store', str(tmp_path / 'store'),
            'capture', '--adapter', str(mapping), '--input', str(source)]
    children = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    for child in children:
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0 and not stderr
        receipt = json.loads(stdout)
        _, raw = store.load(tmp_path / 'store', receipt['snapshot'], config()['scope'])
        assert raw == source.read_bytes()
    assert not list((tmp_path / 'store').glob('.capture-*'))


def test_failed_publication_leaves_no_partial_snapshot(tmp_path, monkeypatch):
    def failed_link(*_args):
        raise OSError('synthetic publication failure')
    monkeypatch.setattr(store.os, 'link', failed_link)
    with pytest.raises(OSError):
        store.save(tmp_path / 'store', raw_data(), config())
    assert list((tmp_path / 'store').iterdir()) == [tmp_path / 'store' / '.lock']


@pytest.mark.parametrize('raw', [b'id,amount,currency\na,1\n', b'id,id,currency\na,1,USD\n',
                                 b'id,amount,currency\na,1,"unclosed'])
def test_malformed_csv_cannot_silently_drop_columns(tmp_path, raw):
    code, result = capture(tmp_path, raw, config('csv'))
    assert code == 1 and set(result) == {'error'}
    assert not (tmp_path / 'store').exists()


def test_configured_retention_survives_process_restart(tmp_path):
    code, rec = capture(tmp_path, None, None, '--retention-days', '90')
    assert code == 0 and rec['expires_at'] - rec['captured_at'] == 90 * 86400
    code, result = cli(tmp_path, 'sum', rec['snapshot'], '--scope', config()['scope'])
    assert code == 0 and result['expires_at'] == rec['expires_at']


def test_failed_producer_does_not_capture_documented_staging_pattern(tmp_path):
    mapping = tmp_path / 'adapter.json'
    mapping.write_text(json.dumps(config()))
    # A valid-looking complete JSON response followed by exporter failure.
    script = '''umask 077
stage=$(mktemp)
trap 'rm -f "$stage"' EXIT
export_readonly() { printf '%s' '{"complete":true,"records":[]}'; return 1; }
if export_readonly > "$stage" 2>/dev/null; then
  "$1" "$2" --store "$3" capture --adapter "$4" --input "$stage"
else
  exit 1
fi
'''
    result = subprocess.run(['bash', '-c', script, 'test', sys.executable,
                             str(SCRIPTS / 'local_data.py'), str(tmp_path / 'store'), str(mapping)],
                            capture_output=True, timeout=10)
    assert result.returncode == 1 and result.stdout == b''
    assert not (tmp_path / 'store').exists()


def test_changed_original_is_not_silently_substituted(tmp_path):
    code, receipt = capture(tmp_path)
    assert code == 0
    (tmp_path / 'source.json').write_bytes(raw_data(0))
    code, result = cli(tmp_path, 'sum', receipt['snapshot'], '--scope', config()['scope'])
    assert code == 0 and result['rows'] == 2
    code, other = capture(tmp_path, raw_data(0))
    assert code == 0 and other['snapshot'] != receipt['snapshot']


def test_wire_numbers_preserve_booleans_null_and_exact_nested_values():
    parsed = contract.parse_json(b'{"x":9007199254740993,"nested":[0.12345678901234567890,true,null]}')
    transported = json.loads(contract.encode(contract.wire(parsed)))
    assert transported == {'x': '9007199254740993', 'nested': ['0.12345678901234567890', True, None]}


def test_corrupt_snapshot_blocks_new_capture_but_not_intact_reads(tmp_path):
    first, _ = store.save(tmp_path / 'store', raw_data(), config(), now=100)
    second, _ = store.save(tmp_path / 'store', raw_data(1), config(), now=100)
    bad = tmp_path / 'store' / (first + '.json')
    bad.write_text('corrupt')
    with pytest.raises(contract.DataError, match='snapshot_changed'):
        store.save(tmp_path / 'store', raw_data(3), config(), now=101)
    _, raw = store.load(tmp_path / 'store', second, config()['scope'], now=101)
    assert raw == raw_data(1) and bad.exists()
    store.delete(tmp_path / 'store', first)
    store.save(tmp_path / 'store', raw_data(3), config(), now=101)
