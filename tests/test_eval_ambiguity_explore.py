"""The ambiguity eval's oracle, prompts and trace must be what the receipt says."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('eval_ambiguity_explore', ROOT / 'scripts/eval_ambiguity_explore.py')
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)
HOOK = importlib.util.spec_from_file_location('analysis_hook', ROOT / 'plugins/llm-accuracy/hooks/analysis-contract-injector.py')


def test_every_definitional_choice_moves_the_july_count():
    counts = evaluation.variants(evaluation.make_rows())
    assert counts == {'reference': 43, 'utc': 41, 'include_test': 48, 'keep_merged': 46, 'trials_count': 47,
                      'signups': 34, 'any_july_start': 49, 'rows_not_accounts': 54, 'blanks_in_july': 45}
    assert evaluation.make_rows() == evaluation.make_rows()


def test_colliding_variants_are_refused(monkeypatch):
    monkeypatch.setattr(evaluation, 'count', lambda rows, **choices: 7)
    with pytest.raises(ValueError, match='fixture_variants_collide'):
        evaluation.variants([])


def test_vague_prompt_fires_the_candidate_reminder_and_precise_prompt_stays_silent():
    sys.path.insert(0, str(ROOT / 'plugins/llm-accuracy/hooks'))
    hook = importlib.util.module_from_spec(HOOK)
    HOOK.loader.exec_module(hook)
    assert hook.is_ambiguous_new_count(evaluation.PROMPTS['vague'])
    assert not hook.should_fire(evaluation.PROMPTS['precise'])


def test_trace_counts_reminders_and_fixture_reads_without_answer_text():
    events = [
        {'type': 'system', 'subtype': 'hook_response', 'stdout': 'x more than one reasonable interpretation x'},
        {'type': 'system', 'subtype': 'hook_response', 'stdout': 'CLAIM FIDELITY CHECK'},
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Read', 'input': {'file_path': '/w/signups.csv'}},
            {'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'ls'}},
            {'type': 'text', 'text': 'secret answer text'}]}},
        {'type': 'result', 'total_cost_usd': 0.123456, 'result': 'secret answer text'},
    ]
    traced = evaluation.trace('\n'.join(json.dumps(e) for e in events) + '\nnot json\n')
    assert traced == {'ambiguity_reminders': 1, 'analysis_reminders': 0, 'hook_responses_seen': 2, 'tool_calls': 2,
                      'tool_calls_by_name': {'Read': 1, 'Bash': 1}, 'fixture_tool_calls': 1, 'cost_usd': 0.1235}
    assert 'secret' not in json.dumps(traced)


def test_live_run_refuses_a_raw_folder_inside_the_repository(capsys):
    with pytest.raises(SystemExit):
        evaluation.main(['--baseline-plugin', str(ROOT / 'plugins/llm-accuracy'), '--raw-dir', str(ROOT / 'raw')])
    assert 'outside the repository' in capsys.readouterr().err
    assert not (ROOT / 'raw').exists()


def test_session_has_no_mcp_servers_and_only_read_tools(tmp_path):
    command = evaluation.session_command(tmp_path, 'claude-sonnet-5-5', 'high')
    assert command[command.index('--tools') + 1] == 'Bash,Read,Grep,Glob'
    assert command[command.index('--mcp-config') + 1] == '{"mcpServers":{}}'
    assert '--strict-mcp-config' in command and '--no-session-persistence' in command
    assert command[command.index('--setting-sources') + 1] == ''
    assert command[-2:] == ['--effort', 'high']
