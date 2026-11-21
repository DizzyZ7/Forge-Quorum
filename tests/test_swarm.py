"""Regression tests for review-first isolated Codex execution."""
from __future__ import annotations

import contextlib
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.swarm import (SwarmError, cleanup_job, create_job,
                                execute_job, inspect_job, list_jobs, plan)


@unittest.skipUnless(shutil.which('git'), 'Git executable required')
class SwarmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'repo'
        self.root.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'tests@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.root/'go.mod').write_text('module example.invalid/app\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial repo')

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, (args, result.stderr))
        return result.stdout.strip()

    def test_plan_no_file_changes_or_git_calls(self):
        original = list(self.root.iterdir())
        with patch('forgequorum.swarm._git') as git:
            result = plan(self.root, 'Write Go API tests', profile='go')
            git.assert_not_called()
        self.assertEqual(result['profile'], 'go')
        self.assertIn('go-engineer', result['agents'])
        self.assertEqual(result['execution'], 'planned-only')
        self.assertEqual(original, list(self.root.iterdir()))

    def test_new_isolated_worktree_and_branch(self):
        job = create_job(self.root, 'Write Go API tests', 'go')
        workspace = Path(job['workspace'])
        self.assertTrue(workspace.is_dir())
        self.assertIn(job['branch'], self.git('branch', '--list', 'forgequorum/*'))
        self.assertEqual(job['base_sha'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(inspect_job(self.root, job['id'])['state'], 'prepared')
        self.assertEqual(len(list_jobs(self.root)), 1)
        self.assertEqual(list(workspace.glob('*.py')), [])

    def test_uncommitted_user_changes_untouched(self):
        (self.root/'go.mod').write_text('my local, do not overwrite')
        job = create_job(self.root, 'Make Go server', 'go')
        self.assertIn('uncommitted changes', job['notice'])
        self.assertEqual((self.root/'go.mod').read_text(), 'my local, do not overwrite')
        self.assertEqual((Path(job['workspace'])/'go.mod').read_text(), 'module example.invalid/app\n')

    def test_run_defaults_to_dry_run(self):
        job = create_job(self.root, 'Make Go API', 'go')
        with patch('forgequorum.swarm._codex_exec') as codex:
            result = execute_job(self.root, job['id'])
            codex.assert_not_called()
        self.assertEqual(result['state'], 'dry-run')
        self.assertEqual(inspect_job(self.root, job['id'])['state'], 'prepared')

    def test_opt_in_execution_records_outcome_not_transcript(self):
        job = create_job(self.root, 'Make Go API', 'go')
        with patch('forgequorum.swarm.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec', return_value=('completed', 0, 4)) as codex:
            result = execute_job(self.root, job['id'], 120, True)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['last_execution']['events_seen'], 4)
        self.assertIn('Do not commit, merge, push', codex.call_args.args[1])
        common = self.root/'.git'/'forgequorum'/'jobs'/f"{job['id']}.json"
        self.assertNotIn('model transcript', common.read_text())

    def test_failure_stays_inspectable(self):
        job = create_job(self.root, 'Write Go API', 'go')
        with patch('forgequorum.swarm.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec', return_value=('failed', 17, 3)):
            result = execute_job(self.root, job['id'], 120, True)
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['last_execution']['exit_code'], 17)
        self.assertTrue(Path(job['workspace']).is_dir())

    def test_cleanup_requires_confirmation_and_clean_tree(self):
        job = create_job(self.root, 'Go endpoint', 'go')
        self.assertEqual(cleanup_job(self.root, job['id'])['state'], 'dry-run')
        workspace = Path(job['workspace'])
        (workspace/'new.txt').write_text('untracked important code')
        with self.assertRaisesRegex(SwarmError, 'uncommitted'):
            cleanup_job(self.root, job['id'], confirm=True)
        self.assertTrue((workspace/'new.txt').exists())
        (workspace/'new.txt').unlink()
        result = cleanup_job(self.root, job['id'], confirm=True)
        self.assertEqual(result['state'], 'cleaned')
        self.assertFalse(workspace.exists())
        self.assertIn(job['branch'], self.git('branch', '--list', job['branch']))

    def test_reject_malicious_identifier_and_metadata(self):
        job = create_job(self.root, 'Go endpoint', 'go')
        with self.assertRaises(SwarmError):
            inspect_job(self.root, '../../etc/passwd')
        path = self.root/'.git'/'forgequorum'/'jobs'/f"{job['id']}.json"
        data = json.loads(path.read_text())
        data['workspace'] = str(self.root)
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(SwarmError, 'does not match'):
            cleanup_job(self.root, job['id'], confirm=True)
        self.assertTrue(self.root.is_dir())

    def test_missing_codex_is_explained_without_running(self):
        job = create_job(self.root, 'Write Go API', 'go')
        with patch('forgequorum.swarm.shutil.which', return_value=None):
            with self.assertRaisesRegex(SwarmError, 'missing'):
                execute_job(self.root, job['id'], execute=True)
        self.assertEqual(inspect_job(self.root, job['id'])['state'], 'prepared')

    def test_cli_commands(self):
        out = StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['swarm','plan','Write Go API tests','--target',str(self.root),'--json']),0)
        self.assertIn('agents', json.loads(out.getvalue()))
        out=StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['swarm','start','Write Go API tests','--target',str(self.root),'--json']),0)
        job = json.loads(out.getvalue())
        out=StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['swarm','run',job['id'],'--target',str(self.root)]),0)
        self.assertEqual(json.loads(out.getvalue())['state'], 'dry-run')

    def test_no_shell_execution_and_jsonl_bounded(self):
        from forgequorum.swarm import _codex_exec
        job = create_job(self.root, 'Write Go API', 'go')
        with patch('forgequorum.swarm.shutil.which',return_value='/fake/codex'), \
             patch('forgequorum.swarm.subprocess.run') as run:
            def fake_run(argv, **kwargs):
                self.assertIsInstance(argv, list)
                self.assertEqual(argv[1:5], ['exec','--json','--sandbox','workspace-write'])
                self.assertFalse(kwargs.get('shell', False))
                kwargs['stdout'].write('{"type":"turn.completed"}\ninvalid\n')
                return type('Result', (), {'returncode':0})()
            run.side_effect=fake_run
            result=_codex_exec(Path(job['workspace']), 'test prompt', 60)
        self.assertEqual(result, ('completed',0,1))


if __name__ == '__main__':
    unittest.main()
