"""Priority-queue and dependency ordering regression tests (no paid model calls)."""
from __future__ import annotations

import contextlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.queue import (enqueue, snapshot, dispatch, reprioritize, requeue,
                               recover, cancel_queued, observe, _claim_next, _repo, _write, _transaction)
from forgequorum.swarm import SwarmError, inspect_job


@unittest.skipUnless(shutil.which('git'), 'git is required')
class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'go.mod').write_text('module example.invalid/test\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial commit')
        self.env = patch.dict(os.environ, FORGEQUORUM_STATE_DIR=str(Path(self.temp.name) / 'scheduler'))
        self.env.start()
        self.addCleanup(self.env.stop)

    def git(self, *args):
        r = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def add(self, name='Create Go service', priority=0, after=None):
        return enqueue(self.repo, name, priority, after, profile='go')

    @contextlib.contextmanager
    def fake_codex(self, status='completed'):
        with patch('forgequorum.queue.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec', return_value=(status, 0 if status == 'completed' else 1, 3,
                 {'source':'codex-jsonl','input_tokens':10,'output_tokens':5,'cached_input_tokens':0,'total_tokens':15, 'partial':False})):
            yield

    def test_add_is_planning_only_and_priority_sorting(self):
        low = self.add('Low priority', -20)
        high = self.add('High priority', 70)
        medium = self.add('Medium priority', 0)
        status = snapshot(self.repo)
        self.assertEqual(status['ready'], 3)
        self.assertEqual([x['id'] for x in status['items']], [high['id'], medium['id'], low['id']])
        self.assertEqual(inspect_job(self.repo, high['id'])['state'], 'prepared')
        with patch('forgequorum.queue.execute_job') as ex:
            preview = dispatch(self.repo, max_jobs=2)
        ex.assert_not_called()
        self.assertEqual(preview['ready_in_priority_order'], [high['id'], medium['id']])
        self.assertFalse(preview['execution_authorized'])

    def test_reprioritize_requires_confirmation(self):
        a = self.add('A', 1)
        self.assertEqual(reprioritize(self.repo, a['id'], 100)['state'], 'dry-run')
        self.assertEqual(snapshot(self.repo)['items'][0]['priority'], 1)
        reprioritize(self.repo, a['id'], 100, confirm=True)
        self.assertEqual(snapshot(self.repo)['items'][0]['priority'], 100)
        with self.assertRaises(SwarmError):
            reprioritize(self.repo, a['id'], 101, True)

    def test_dependencies_order_execution_but_not_code_propagation(self):
        first = self.add('API schema', 0)
        second = self.add('Go tests', 100, [first['id']])
        self.assertEqual(snapshot(self.repo)['ready'], 1)
        with self.fake_codex():
            result = dispatch(self.repo, max_jobs=2, parallel=2, execute=True)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['jobs_started'], 2)
        self.assertEqual({x['state'] for x in snapshot(self.repo)['items']}, {'completed'})
        # Worktrees are isolated: dependencies are execution-order only.
        (Path(first['workspace']) / 'generated.txt').write_text('independent edit')
        self.assertFalse((Path(second['workspace']) / 'generated.txt').exists())

    def test_failed_dependency_blocks_and_manual_retry(self):
        a = self.add('A')
        b = self.add('B', 10, [a['id']])
        with self.fake_codex('failed'):
            result = dispatch(self.repo, max_jobs=2, execute=True)
        self.assertEqual(result['state'], 'partial-failure')
        self.assertEqual(result['jobs_started'], 1)
        states = {x['id']: x['readiness'] for x in snapshot(self.repo)['items']}
        self.assertEqual(states[b['id']], 'dependency-failed')
        self.assertEqual(requeue(self.repo, a['id'])['state'], 'dry-run')
        requeue(self.repo, a['id'], True)
        with self.fake_codex():
            self.assertEqual(dispatch(self.repo, max_jobs=2, execute=True)['state'], 'completed')
        self.assertEqual(snapshot(self.repo)['ready'], 0)

    def test_cancel_queued_preserves_workspace_and_blocks_dependents(self):
        parent = self.add('First')
        child = self.add('Second', after=[parent['id']])
        self.assertEqual(cancel_queued(self.repo, parent['id'])['state'], 'dry-run')
        self.assertEqual(cancel_queued(self.repo, parent['id'], True)['state'], 'cancelled')
        self.assertEqual(snapshot(self.repo)['ready'], 0)
        entry = next(x for x in snapshot(self.repo)['items'] if x['id'] == child['id'])
        self.assertEqual(entry['readiness'], 'dependency-failed')
        self.assertTrue(Path(parent['workspace']).is_dir())
        with self.assertRaises(SwarmError):
            cancel_queued(self.repo, parent['id'], True)

    def test_foreground_watch_uses_changing_snapshots_only(self):
        item = self.add('Work')
        observations = list(observe(self.repo, seconds=.21, interval=.1))
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]['items'][0]['id'], item['id'])
        with self.assertRaises(SwarmError):
            list(observe(self.repo, seconds=301))

    def test_unknown_or_future_dependency_refused_before_workspace_creation(self):
        with self.assertRaisesRegex(SwarmError, 'Dependencies'):
            self.add('Cannot start', after=['000000000000'])
        self.assertEqual(len(list(self.repo.parent.glob('.forgequorum-worktrees/repo/*'))), 0)
        a = self.add('A')
        with self.assertRaises(SwarmError):
            self.add('Duplicate', after=[a['id'], a['id']])

    def test_no_codex_never_claims(self):
        item = self.add('A')
        with patch('forgequorum.queue.shutil.which', return_value=None):
            with self.assertRaisesRegex(SwarmError, 'Codex CLI missing'):
                dispatch(self.repo, execute=True)
        self.assertEqual(snapshot(self.repo)['items'][0]['state'], 'queued')

    def test_claim_survives_other_dispatched_runner(self):
        a = self.add('A')
        b = self.add('B')
        _, common = _repo(self.repo)
        claimed = _claim_next(self.repo, common)
        self.assertEqual(claimed[0], a['id'])
        self.assertEqual(snapshot(self.repo)['ready'], 1)
        # Another run cannot claim the first job, but may select the second.
        self.assertEqual(_claim_next(self.repo, common)[0], b['id'])
        self.assertEqual(snapshot(self.repo)['ready'], 0)
        with self.assertRaisesRegex(SwarmError, 'still alive'):
            recover(self.repo, a['id'], True)

    def test_dead_claim_recovery_is_manual_and_preserves_other_worktrees(self):
        a = self.add('A')
        _, common = _repo(self.repo)
        _claim_next(self.repo, common)
        with _transaction(common) as (folder, data):
            data['entries'][a['id']]['claim']['pid'] = 999999999
            _write(folder, data)
        self.assertEqual(recover(self.repo, a['id'])['state'], 'dry-run')
        self.assertEqual(snapshot(self.repo)['items'][0]['state'], 'claimed')
        self.assertEqual(recover(self.repo, a['id'], True)['state'], 'failed')
        requeue(self.repo, a['id'], True)
        self.assertTrue(Path(a['workspace']).exists())

    def test_queue_metadata_symlink_refused(self):
        a = self.add('A')
        _, common = _repo(self.repo)
        path = common / 'forgequorum' / 'queue.json'
        backup = path.with_name('backup.json')
        path.rename(backup)
        try:
            path.symlink_to(backup)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink not available')
        with self.assertRaisesRegex(SwarmError, 'symlinked'):
            snapshot(self.repo)
        self.assertTrue(Path(a['workspace']).exists())

    def test_corrupted_queue_refused(self):
        self.add('A')
        _, common = _repo(self.repo)
        path = common / 'forgequorum' / 'queue.json'
        data = json.loads(path.read_text())
        data['entries'][next(iter(data['entries']))]['state'] = 'not-a-state'
        path.write_text(json.dumps(data))
        with self.assertRaises(SwarmError):
            snapshot(self.repo)

    def test_cli_add_status_and_run_preview(self):
        output = StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['queue', 'add', 'Create a Go endpoint', '--target', str(self.repo),
                                   '--profile', 'go', '--priority', '8']), 0)
        job = json.loads(output.getvalue())
        output = StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['queue', 'status', '--target', str(self.repo)]), 0)
        self.assertEqual(json.loads(output.getvalue())['items'][0]['id'], job['id'])
        output = StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['queue', 'run', '--target', str(self.repo)]), 0)
        self.assertEqual(json.loads(output.getvalue())['state'], 'dry-run')

    def test_cross_process_queue_claim_is_persistent(self):
        a = self.add('A')
        script = 'from forgequorum.queue import _claim_next, _repo; from pathlib import Path; root, common = _repo(Path(__import__("sys").argv[1])); print(_claim_next(root, common))'
        out = subprocess.run([sys.executable, '-c', script, str(self.repo)], capture_output=True,
                             text=True, timeout=15,
                             env={**os.environ, 'PYTHONPATH':str(Path(__file__).parents[1]/'src')})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(a['id'], out.stdout)
        self.assertEqual(snapshot(self.repo)['ready'], 0)
        recover(self.repo, a['id'], True)
        self.assertTrue(Path(a['workspace']).exists())


if __name__ == '__main__':
    unittest.main()
