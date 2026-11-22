"""v0.11: declarative workflows, metadata events, read-only dashboards, quality policies."""
import contextlib
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.queue import _repo, _transaction, _write, dashboard, events, enqueue, snapshot, reprioritize, cancel_queued, MAX_EVENTS
from forgequorum.queue_dashboard import export, render
from forgequorum.quality import run_verification
from forgequorum.quality_policy import read_policy
from forgequorum.swarm import SwarmError
from forgequorum.workflows import workflow, PartialWorkflowError


class WorkflowsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name) / 'repo'
        self.repo.mkdir()
        for args in [('init', '-q', '-b', 'main'), ('config', 'user.name', 'Test'),
                     ('config', 'user.email', 'test@example.invalid')]:
            self.git(*args)
        (self.repo / 'go.mod').write_text('module example.invalid/forge\n', encoding='utf8')
        self.git('add', '.')
        self.git('commit', '-qm', 'initial')
        self.recipe = Path(temp.name) / 'plan.json'
        self.write_steps([
            {'key': 'api', 'task': 'Build Go API', 'profile': 'go', 'priority': 10},
            {'key': 'tests', 'task': 'Test Go API', 'profile': 'go', 'after': ['api'], 'gate': 'verified'},
        ])

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write_steps(self, steps):
        self.recipe.write_text(json.dumps({'schema': 1, 'steps': steps}), encoding='utf8')

    def test_preview_is_read_only_and_retains_label_dependencies(self):
        before = self.git('status', '--porcelain')
        result = workflow(self.repo, self.recipe)
        self.assertEqual(result['state'], 'dry-run')
        self.assertEqual(result['steps'][1]['after'], ['api'])
        self.assertFalse((self.repo / '.git/forgequorum').exists())
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_apply_creates_worktrees_without_codex(self):
        result = workflow(self.repo, self.recipe, apply=True)
        ids = result['job_ids']
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(ids['api'], ids['tests'])
        data = snapshot(self.repo)
        self.assertEqual(data['ready'], 1)
        self.assertEqual([item['gate'] for item in data['items']], ['order', 'verified'])
        self.assertEqual(next(item['after'] for item in data['items'] if item['id'] == ids['tests']), [ids['api']])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual([ev['kind'] for ev in events(self.repo)['events']], ['queued', 'queued'])

    def test_unknown_fields_future_and_duplicate_steps_refused_before_writes(self):
        invalid = [
            [{'key': 'a', 'task': 'A', 'after': ['missing']}],
            [{'key': 'a', 'task': 'A'}, {'key': 'a', 'task': 'B'}],
            [{'key': 'a', 'task': 'A', 'profile': '__import__'}],
            [{'key': 'a', 'task': 'A', 'priority': True}],
            [{'key': 'a', 'task': 'A', 'gate': 'transferred'}],
            [{'key': 'b', 'task': 'B', 'after': ['a']}, {'key': 'a', 'task': 'A', 'after': ['b']}],
            [{'key': 'a', 'task': 'A', 'unexpected': 'ignored'}],
        ]
        for steps in invalid:
            with self.subTest(steps=steps):
                self.write_steps(steps)
                with self.assertRaises(SwarmError):
                    workflow(self.repo, self.recipe, apply=True)
                self.assertFalse((self.repo / '.git/forgequorum').exists())

    def test_symlink_and_oversized_recipe_refused(self):
        self.recipe.write_bytes(b'a' * (64 * 1024 + 1))
        with self.assertRaises(SwarmError):
            workflow(self.repo, self.recipe)
        self.recipe.unlink()
        try:
            self.recipe.symlink_to(self.repo / 'go.mod')
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(SwarmError):
            workflow(self.repo, self.recipe)

    def test_partial_apply_error_lists_created_worktree_ids(self):
        from forgequorum import workflows as module
        original = module.enqueue
        count = 0

        def flaky(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise SwarmError('simulated full disk')
            return original(*args, **kwargs)

        with patch('forgequorum.workflows.enqueue', side_effect=flaky):
            with self.assertRaises(PartialWorkflowError) as error:
                workflow(self.repo, self.recipe, apply=True)
        self.assertIn('api', error.exception.created)
        self.assertTrue(len(snapshot(self.repo)['items']) == 1)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_cli_workflow_preview_then_apply(self):
        out = StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['workflow', str(self.recipe), '--target', str(self.repo)]), 0)
        self.assertEqual(json.loads(out.getvalue())['state'], 'dry-run')
        self.assertFalse((self.repo / '.git/forgequorum').exists())
        with contextlib.redirect_stdout(StringIO()):
            self.assertEqual(main(['workflow', str(self.recipe), '--target', str(self.repo), '--apply']), 0)
        self.assertEqual(snapshot(self.repo)['total'], 2)

    def test_events_and_dashboard_are_no_transcript_metadata(self):
        a = enqueue(self.repo, 'SECRET PROMPT DO NOT LOG', profile='go')
        reprioritize(self.repo, a['id'], 10, confirm=True)
        assert cancel_queued(self.repo, a['id'], confirm=True)['state'] == 'cancelled'
        recent = events(self.repo)
        self.assertEqual([x['kind'] for x in recent['events']], ['queued', 'reprioritized', 'cancelled'])
        self.assertNotIn('SECRET', json.dumps(recent))
        board = dashboard(self.repo)
        self.assertEqual(board['states']['cancelled'], 1)
        self.assertEqual(board['ready'], 0)
        self.assertEqual(events(self.repo, 1)['returned'], 1)
        with self.assertRaises(SwarmError):
            events(self.repo, 501)

    def test_event_rollover_and_corrupt_data_are_detected(self):
        a = enqueue(self.repo, 'A', profile='go')
        _, common = _repo(self.repo)
        with _transaction(common) as (folder, data):
            data['events'] = [{'at': '2026-11-22', 'kind': 'queued', 'job_id': a['id']}] * MAX_EVENTS
            _write(folder, data)
        reprioritize(self.repo, a['id'], 12, confirm=True)
        self.assertEqual(events(self.repo, 500)['retained'], MAX_EVENTS)
        with _transaction(common) as (folder, data):
            data['events'][-1]['kind'] = ['corrupt']
            with self.assertRaises(SwarmError):
                _write(folder, data)
        self.assertEqual(snapshot(self.repo)['total'], 1)

    def test_static_dashboard_escapes_html_and_refuses_overwrite(self):
        raw = {'total': 1, 'ready': 0, 'states': {'<script>alert(1)</script>': 1},
               'items': [{'id': '<img src=x onerror=1>', 'state': 'queued', 'readiness': 'ready',
                          'priority': 1, 'gate': 'order', 'after': []}]}
        html = render(raw)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)
        file = self.recipe.parent / 'dashboard.html'
        result = export(self.repo, file)
        self.assertTrue(file.is_file())
        self.assertEqual(result['total'], 0)
        with self.assertRaises(SwarmError):
            export(self.repo, file)
        out = StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['queue', 'dashboard', '--target', str(self.repo)]), 0)
        self.assertEqual(json.loads(out.getvalue())['ready'], 0)


class QualityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'go.mod').write_text('module example.invalid/testing\n', encoding='utf8')

    def policy(self, gates):
        (self.root / 'forgequorum.quality.json').write_text(
            json.dumps({'schema': 1, 'required_gates': gates}), encoding='utf8')

    def test_missing_gate_blocks_success_even_when_another_test_passes(self):
        self.policy(['cargo-test'])
        with patch('forgequorum.quality.shutil.which', return_value='/usr/bin/go'), \
             patch('forgequorum.quality.subprocess.run') as runner:
            runner.return_value.returncode = 0
            result = run_verification(self.root, run=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['quality_policy']['missing_gates'], ['cargo-test'])
        self.assertEqual(result['results'][0]['status'], 'passed')

    def test_required_real_gate_passes(self):
        self.policy(['go-test'])
        with patch('forgequorum.quality.shutil.which', return_value='/usr/bin/go'), \
             patch('forgequorum.quality.subprocess.run') as runner:
            runner.return_value.returncode = 0
            result = run_verification(self.root, run=True)
        self.assertTrue(result['ok'])
        self.assertEqual(result['quality_policy']['required_gates'], ['go-test'])

    def test_unconfigured_gate_is_read_only_and_default(self):
        planned = run_verification(self.root)
        self.assertTrue(planned['quality_policy']['ok'])
        self.assertEqual(planned['quality_policy']['required_gates'], [])

    def test_policy_rejects_shell_commands_unknown_gates_duplicates_and_boolean_schema(self):
        for content in ('{"schema":true,"required_gates":["go-test"]}',
                        '{"schema":1,"required_gates":["rm -rf /"]}',
                        '{"schema":1,"required_gates":["go-test","go-test"]}',
                        '{"schema":1,"required_gates":[]}'):
            with self.subTest(content=content):
                (self.root / 'forgequorum.quality.json').write_text(content, encoding='utf8')
                with self.assertRaises(ValueError):
                    read_policy(self.root)

    def test_symlink_policy_refused(self):
        file = self.root / 'forgequorum.quality.json'
        try:
            file.symlink_to(self.root / 'go.mod')
        except (OSError, NotImplementedError):
            self.skipTest('No symlink permission')
        with self.assertRaises(ValueError):
            run_verification(self.root)


if __name__ == '__main__':
    unittest.main()
