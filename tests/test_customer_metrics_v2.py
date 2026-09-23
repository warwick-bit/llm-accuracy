import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import eval_customer_metrics_v2 as v2


def fixture_answer():
    fixture = json.loads((v2.pilot.EXAMPLE / 'fixture.json').read_text())
    expected = v2.pilot.expected_rows(fixture)
    answer = {'decision': 'needs_correction', 'verified_metrics': [
        {k: row[k] for k in v2.pilot.METRICS} for row in expected],
        'Checked': 'Synthetic.', 'Gap': 'Fixture only.', 'Next': 'None.'}
    return expected, answer


@pytest.mark.parametrize('fence', [False, True])
@pytest.mark.parametrize('mutation', ['none', 'verdict', 'count', 'money', 'omit', 'duplicate', 'null_zero'])
def test_rendering_does_not_relax_quality(fence, mutation):
    expected, value = fixture_answer()
    if mutation == 'verdict':
        value['decision'] = 'supported'
    elif mutation == 'count':
        value['verified_metrics'][0]['number_of_orders'] = 3
    elif mutation == 'money':
        value['verified_metrics'][0]['customer_lifetime_value'] = 91
    elif mutation == 'omit':
        value['verified_metrics'].pop()
    elif mutation == 'duplicate':
        value['verified_metrics'].append(dict(value['verified_metrics'][0]))
    elif mutation == 'null_zero':
        value['verified_metrics'][-1]['number_of_orders'] = 0
    text = json.dumps(value)
    if fence:
        text = '```json\n' + text + '\n```'
    result = v2.score(text, expected, 'needs_correction')
    assert result['scorable']
    assert result['all_scored_fields_correct'] is (mutation == 'none')


@pytest.mark.parametrize('text,category', [
    ('{} {}', 'json_decode'), ('Preface {}', 'json_decode'),
    ('```json\n{}\n```\nSupported.', 'json_decode'),
    ('{"decision":"supported","decision":"needs_correction"}', 'json_decode'),
    ('{"x":NaN}', 'json_decode'), ('{"x":Infinity}', 'json_decode'),
    ('[]', 'root_type'), ('{}', 'root_keys')])
def test_ambiguous_or_invalid_output_is_unscored(text, category):
    assert v2.score(text, [], 'supported')['failure'] == category


def test_prompt_delta_is_shared_and_has_no_answer_values():
    fixture = json.loads((v2.pilot.EXAMPLE / 'fixture.json').read_text())
    sql = (v2.pilot.EXAMPLE / v2.pilot.VARIANTS[1]).read_text()
    suffixes = []
    for arm in v2.pilot.ARMS:
        base = v2.pilot.make_prompt(sql, fixture, arm)
        prompt = v2.make_prompt(sql, fixture, arm)
        assert prompt.startswith(base)
        suffixes.append(prompt[len(base):])
    assert suffixes[0] == suffixes[1]
    assert '"verified_metrics": []' in suffixes[0]


def test_pair_stops_on_failure_and_persists_only_metadata(monkeypatch, tmp_path):
    calls = []
    def fail(prompt, model):
        calls.append(1)
        return {'status': 'timeout', 'answers': ['MUST NOT PERSIST']}
    monkeypatch.setattr(v2.pilot, 'run_review', fail)
    receipt = {'rows': []}
    fixture = json.loads((v2.pilot.EXAMPLE / 'fixture.json').read_text())
    path = tmp_path / 'receipt.json'
    assert not v2.run_pair(v2.pilot.VARIANTS[0], fixture, 'test', receipt, path)
    assert len(calls) == 1
    assert 'MUST NOT PERSIST' not in path.read_text()
    assert receipt['rows'][0]['score']['failure'] == 'runtime_attestation'
