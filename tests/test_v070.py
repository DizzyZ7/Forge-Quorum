"""v0.7 operations: explicit consent, privacy, cross-platform-safe state changes."""
from __future__ import annotations

import contextlib
from io import StringIO
import json
import os
import sys
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.swarm import SwarmError, create_job, execute_job, inspect_job, _write_job
from forgequorum.swarm_control import request_cancel, recovery, conflicts, verify_job, usage_report


@unittest.skipUnless(shutil.which('git'), 'Git required')
class ControlsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'CI')
        self.git('config', 'user.email', 'ci@example.invalid')
        (self.root / 'go.mod').write_text('module example.invalid/app\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial')

    def git(self, *args, worktree=None):
        result = subprocess.run(['git', '-C', str(worktree or self.root), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, (args, result.stderr))
        return result.stdout

    def job(self):
        return create_job(self.root, 'Build a Go API', profile='go')

    def test_cancel_prepared_preview_and_confirm(self):
        job = self.job()
        preview = request_cancel(self.root, job['id'])
        self.assertEqual(preview['state'], 'dry-run')
        self.assertEqual(inspect_job(self.root, job['id'])['state'], 'prepared')
        outcome = request_cancel(self.root, job['id'], confirm=True)
        self.assertEqual(outcome['state'], 'cancelled')
        self.assertTrue(Path(job['workspace']).exists())
        with self.assertRaisesRegex(SwarmError, 'not runnable'):
            execute_job(self.root, job['id'], execute=True)

    def test_running_cancel_request_is_cooperative(self):
        job = self.job()
        started = threading.Event()
        errors = []
        outcome = {}
        def fake_exec(workspace, prompt, timeout):
            started.set()
            cancel = self.root / '.git' / 'forgequorum' / 'jobs' / (job['id'] + '.cancel')
            for _ in range(100):
                if cancel.exists():
                    cancel.unlink()
                    return ('cancelled', 130, 1, {'source': 'not-reported', 'total_tokens': 0,
                                                   'input_tokens': 0, 'cached_input_tokens': 0,
                                                   'output_tokens': 0, 'partial': True})
                time.sleep(.01)
            raise AssertionError('Cancellation not received')
        def worker():
            try:
                outcome.update(execute_job(self.root, job['id'], execute=True))
            except Exception as exc:
                errors.append(exc)
        with patch('forgequorum.swarm.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec', side_effect=fake_exec):
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(started.wait(4))
            self.assertEqual(request_cancel(self.root, job['id'])['state'], 'dry-run')
            self.assertEqual(request_cancel(self.root, job['id'], True)['state'], 'cancel-requested')
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)
        self.assertEqual(outcome['state'], 'cancelled')
        self.assertEqual(outcome['last_execution']['exit_code'], 130)
        self.assertFalse((self.root / '.git' / 'forgequorum' / 'jobs' / f"{job['id']}.lock").exists())

    def test_recover_refuses_existing_lock_and_preserves_state(self):
        job = self.job()
        common = self.root / '.git'
        record = inspect_job(self.root, job['id'])
        record['state'] = 'running'
        _write_job(common, record)
        lock = common / 'forgequorum' / 'jobs' / f"{job['id']}.lock"
        lock.write_text('unknown owner')
        with self.assertRaisesRegex(SwarmError, 'lock'):
            recovery(self.root, job['id'], True)
        self.assertTrue(lock.exists())
        self.assertEqual(inspect_job(self.root, job['id'])['state'], 'running')

    def test_recover_is_explicit_and_preserves_changes(self):
        job = self.job()
        work = Path(job['workspace'])
        (work / 'my-work.go').write_text('// my work')
        record = inspect_job(self.root, job['id'])
        record['state'] = 'running'
        _write_job(self.root / '.git', record)
        self.assertEqual(recovery(self.root, job['id'])['state'], 'dry-run')
        self.assertEqual(recovery(self.root, job['id'], True)['state'], 'interrupted')
        self.assertEqual((work / 'my-work.go').read_text(), '// my work')
        with self.assertRaises(SwarmError):
            execute_job(self.root, job['id'], execute=True)

    def test_no_conflict_for_independent_paths(self):
        a, b = self.job(), self.job()
        (Path(a['workspace']) / 'a.go').write_text('package a')
        (Path(b['workspace']) / 'b.go').write_text('package b')
        report = conflicts(self.root, [a['id'], b['id']])
        self.assertFalse(report['has_overlaps'])
        self.assertEqual(report['file_counts'][a['id']], 1)
        self.assertEqual(report['file_counts'][b['id']], 1)

    def test_conflict_for_both_untracked_and_modified(self):
        a, b = self.job(), self.job()
        for job in (a, b):
            w = Path(job['workspace'])
            (w / 'go.mod').write_text('module another.invalid/revised\n')
            (w / ' shared name.txt').write_text('private source')
        report = conflicts(self.root, [a['id'], b['id']])
        self.assertTrue(report['has_overlaps'])
        self.assertEqual(report['overlaps'][0]['paths'], [' shared name.txt', 'go.mod'])
        self.assertNotIn('private source', json.dumps(report))

    def test_conflict_for_committed_changes(self):
        a, b = self.job(), self.job()
        for job in (a,b):
            work = Path(job['workspace'])
            (work / 'go.mod').write_text('module changed.invalid/app\n')
            self.git('add', '.', worktree=work)
            self.git('commit', '-qm', 'Change', worktree=work)
        report = conflicts(self.root, [a['id'], b['id']])
        self.assertEqual(report['overlaps'][0]['paths'], ['go.mod'])

    def test_conflicts_reject_bad_identifiers_without_writes(self):
        a,b = self.job(), self.job()
        for ids in ([a['id']], [a['id'], a['id']], [a['id'], '../../bad']):
            with self.assertRaises(SwarmError):
                conflicts(self.root, ids)
        self.assertEqual(inspect_job(self.root, a['id'])['state'], 'prepared')
        self.assertEqual(inspect_job(self.root, b['id'])['state'], 'prepared')

    def test_verify_preview_never_runs_and_records_no_result(self):
        job = self.job()
        with patch('forgequorum.swarm_control.run_verification', return_value={
            'gates': [{'name':'go-test'}], 'executed':False, 'planned':1}) as verifier:
            report = verify_job(self.root, job['id'])
        self.assertEqual(report['state'], 'dry-run')
        self.assertFalse(verifier.call_args.kwargs['run'])
        self.assertNotIn('last_verification', inspect_job(self.root, job['id']))

    def test_verify_requires_run_and_saves_machine_readable_report(self):
        job = self.job()
        mock_result={'ok':True,'results':[{'name':'go-test','status':'passed','exit_code':0}],
                     'planned':1,'executed':True}
        with patch('forgequorum.swarm_control.run_verification', return_value=mock_result) as verifier:
            report = verify_job(self.root, job['id'], run=True)
        self.assertEqual(report['state'], 'passed')
        self.assertTrue(verifier.call_args.kwargs['run'])
        stored = inspect_job(self.root, job['id'])['last_verification']
        self.assertTrue(stored['ok'])
        self.assertEqual(stored['gates'][0]['name'], 'go-test')
        self.assertTrue(Path(job['workspace']).exists())

    def test_verify_refuses_while_running_or_locked(self):
        job = self.job()
        common = self.root / '.git'
        lock = common / 'forgequorum' / 'jobs' / f"{job['id']}.lock"
        lock.write_text('locked')
        with self.assertRaisesRegex(SwarmError, 'running or locked'):
            verify_job(self.root, job['id'], run=True)
        lock.unlink()
        j=inspect_job(self.root, job['id'])
        j['state']='running'
        _write_job(common, j)
        with self.assertRaisesRegex(SwarmError, 'running or locked'):
            verify_job(self.root, job['id'], run=True)

    def test_cli_review_controls(self):
        a,b=self.job(),self.job()
        for cmd in (
            ['swarm','cancel',a['id'],'--target',str(self.root)],
            ['swarm','conflicts',a['id'],b['id'],'--target',str(self.root)],
            ['swarm','verify',a['id'],'--target',str(self.root)],
        ):
            stream=StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(cmd),0)
            self.assertIsInstance(json.loads(stream.getvalue()),dict)

    def test_usage_summary_counts_reported_only(self):
        jobs=[self.job(),self.job()]
        with patch('forgequorum.swarm.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec', return_value=('completed', 0, 2, {
                 'source':'codex-jsonl', 'input_tokens':10,'cached_input_tokens':3,
                 'output_tokens':7,'total_tokens':17, 'partial':False})):
            execute_job(self.root,jobs[0]['id'],execute=True)
        report=usage_report(self.root)
        self.assertEqual(report['totals']['total_tokens'],17)
        self.assertEqual(len(report['jobs_with_reported_usage']),1)
        self.assertEqual(report['jobs_without_reported_usage'],[jobs[1]['id']])
        self.assertNotIn('cost',report)

    def test_usage_is_reported_not_priced(self):
        job = self.job()
        with patch('forgequorum.swarm.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec', return_value=('completed', 0, 5, {
                 'source':'codex-jsonl', 'input_tokens':100,'cached_input_tokens':30,
                 'output_tokens':20, 'total_tokens':120, 'partial':False})):
            result=execute_job(self.root,job['id'],execute=True)
        usage=result['last_execution']['usage']
        self.assertEqual(usage['total_tokens'],120)
        self.assertNotIn('cost', usage)

    @unittest.skipIf(os.name == 'nt', 'POSIX executable smoke test')
    def test_real_child_process_is_cancelled_and_usage_not_faked(self):
        script = Path(self.tmp.name) / 'codex-simulator'
        script.write_text(
            f'#!{sys.executable}\n'
            'import json,sys,time\n'
            'assert sys.stdin.read().startswith("You are working")\n'
            'print(json.dumps({"type":"turn.started"}), flush=True)\n'
            'time.sleep(20)\n'
        )
        script.chmod(0o755)
        job = self.job()
        outcome = {}
        failures = []
        def worker():
            try:
                outcome.update(execute_job(self.root, job['id'], timeout=30, execute=True))
            except Exception as exc:
                failures.append(exc)
        with patch('forgequorum.swarm.shutil.which', return_value=str(script)):
            th = threading.Thread(target=worker)
            th.start()
            marker = self.root / '.git' / 'forgequorum' / 'jobs' / f"{job['id']}.lock"
            for _ in range(200):
                if marker.exists():
                    break
                time.sleep(.01)
            self.assertTrue(marker.exists())
            self.assertEqual(request_cancel(self.root, job['id'], True)['state'], 'cancel-requested')
            th.join(8)
        self.assertFalse(th.is_alive(), 'Child did not stop after requested cancellation')
        self.assertFalse(failures, failures)
        self.assertEqual(outcome['state'], 'cancelled')
        self.assertEqual(outcome['last_execution']['usage']['source'], 'not-reported')
        self.assertTrue(Path(job['workspace']).exists())

    def test_cleanup_refuses_claim_lock(self):
        from forgequorum.swarm import cleanup_job
        job=self.job()
        lock=self.root/'.git'/'forgequorum'/'jobs'/f"{job['id']}.lock"
        lock.write_text('existing lock')
        with self.assertRaisesRegex(SwarmError, 'locked'):
            cleanup_job(self.root,job['id'],confirm=True)
        self.assertTrue(Path(job['workspace']).exists())


if __name__ == '__main__':
    unittest.main()
