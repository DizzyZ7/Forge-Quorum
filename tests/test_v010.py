"""End-to-end tests for explicit verified/transfer dependencies using real Git worktrees."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.queue import enqueue, snapshot, dispatch, _transaction, _write, _repo
from forgequorum.swarm import SwarmError, _load_job, _write_job
from forgequorum.swarm_control import verify_job
from forgequorum.transfer import transfer


class TransferTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / 'repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-q', '-b', 'main')
        self.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.git(self.repo, 'config', 'user.name', 'Test')
        (self.repo / 'go.mod').write_text('module example.invalid/test\n', encoding='utf-8')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-qm', 'Initial')
        self.config = patch.dict(os.environ, FORGEQUORUM_STATE_DIR=str(Path(tmp.name) / 'scheduler'))
        self.config.start()
        self.addCleanup(self.config.stop)

    def git(self, folder, *args):
        result = subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def add(self, name, after=None, gate='order'):
        return enqueue(self.repo, name, after=after, profile='go', gate=gate)

    def mark_parent_completed(self, parent, filename='api.txt', content='result\n', verify=True, passed=True):
        workspace = Path(parent['workspace'])
        (workspace / filename).write_text(content, encoding='utf-8')
        self.git(workspace, 'add', filename)
        self.git(workspace, 'commit', '-qm', 'Completed parent implementation')
        root, common = _repo(self.repo)
        with _transaction(common) as (folder, data):
            data['entries'][parent['id']]['state'] = 'completed'
            _write(folder, data)
        job = _load_job(root, common, parent['id'])
        job['state'] = 'completed'
        _write_job(common, job)
        if verify:
            fake = {'ok': passed, 'results': [{'name': 'go-test', 'status': 'passed' if passed else 'failed',
                                               'exit_code': 0 if passed else 1}]}
            with patch('forgequorum.swarm_control.run_verification', return_value=fake):
                verify_job(self.repo, parent['id'], run=True)
        return workspace

    def readiness(self, child):
        return next(x['readiness'] for x in snapshot(self.repo)['items'] if x['id'] == child['id'])

    def test_strict_verified_gate_blocks_until_fresh_successful_check(self):
        parent = self.add('API')
        child = self.add('Tests', [parent['id']], gate='verified')
        self.assertEqual(self.readiness(child), 'waiting-for-dependencies')
        workspace = self.mark_parent_completed(parent, verify=False)
        self.assertEqual(self.readiness(child), 'dependency-unverified')
        with patch('forgequorum.swarm_control.run_verification', return_value={'ok': False, 'results': [{'name':'test','status':'failed'}]}):
            verify_job(self.repo, parent['id'], run=True)
        self.assertEqual(self.readiness(child), 'dependency-unverified')
        with patch('forgequorum.swarm_control.run_verification', return_value={'ok': True, 'results': [{'name':'test','status':'passed'}]}):
            verify_job(self.repo, parent['id'], run=True)
        self.assertEqual(self.readiness(child), 'ready')
        (workspace / 'api.txt').write_text('changed after verified')
        self.assertEqual(self.readiness(child), 'dependency-unverified')

    def test_explicit_verified_transfer_does_not_touch_main(self):
        parent = self.add('API')
        child = self.add('Consumers', [parent['id']], gate='transferred')
        source = self.mark_parent_completed(parent)
        dest = Path(child['workspace'])
        self.assertEqual(self.readiness(child), 'handoff-required')
        preview = transfer(self.repo, child['id'], parent['id'])
        self.assertEqual(preview['state'], 'dry-run')
        self.assertEqual(preview['paths'], ['api.txt'])
        self.assertFalse((dest / 'api.txt').exists())
        self.assertFalse((self.repo / 'api.txt').exists())
        self.assertEqual(self.readiness(child), 'handoff-required')
        result = transfer(self.repo, child['id'], parent['id'], apply=True)
        self.assertEqual(result['state'], 'staged')
        self.assertEqual((dest / 'api.txt').read_text(), 'result\n')
        self.assertEqual(self.git(dest, 'diff', '--cached', '--name-only'), 'api.txt')
        self.assertEqual(self.git(dest, 'branch', '--show-current'), 'forgequorum/'+child['id'])
        self.assertEqual(self.git(self.repo, 'status', '--porcelain'), '')
        self.assertEqual(self.readiness(child), 'ready')
        with self.assertRaisesRegex(SwarmError, 'already been transferred'):
            transfer(self.repo, child['id'], parent['id'], apply=True)
        self.assertEqual((source / 'api.txt').read_text(), 'result\n')

    def test_child_with_tampered_staged_or_unstaged_changes_is_blocked(self):
        parent = self.add('API')
        child = self.add('Consume', [parent['id']], gate='transferred')
        self.mark_parent_completed(parent)
        transfer(self.repo, child['id'], parent['id'], apply=True)
        dest = Path(child['workspace'])
        (dest / 'api.txt').write_text('corrupt unstaged content')
        self.assertEqual(self.readiness(child), 'handoff-stale')
        self.git(dest, 'add', 'api.txt')
        self.assertEqual(self.readiness(child), 'handoff-stale')
        with self.assertRaisesRegex(SwarmError, 'already been transferred'):
            transfer(self.repo, child['id'], parent['id'], apply=True)

    def test_multi_dependency_different_files_succeeds_and_blocks_before_all(self):
        a = self.add('API')
        b = self.add('DOCS')
        c = self.add('Consumer', [a['id'], b['id']], gate='transferred')
        self.mark_parent_completed(a, 'api.txt', 'api')
        self.mark_parent_completed(b, 'docs.txt', 'docs')
        transfer(self.repo, c['id'], a['id'], apply=True)
        self.assertEqual(self.readiness(c), 'handoff-required')
        transfer(self.repo, c['id'], b['id'], apply=True)
        self.assertEqual(self.readiness(c), 'ready')
        self.assertEqual(self.git(Path(c['workspace']), 'diff', '--cached', '--name-only'), 'api.txt\ndocs.txt')
        self.assertFalse((self.repo / 'api.txt').exists())
        self.assertFalse((self.repo / 'docs.txt').exists())

    def test_same_filename_overlap_rejected_without_losing_first_transfer(self):
        a = self.add('One')
        b = self.add('Two')
        c = self.add('Consume', [a['id'], b['id']], gate='transferred')
        self.mark_parent_completed(a, 'shared.txt', 'A')
        self.mark_parent_completed(b, 'shared.txt', 'B')
        transfer(self.repo, c['id'], a['id'], apply=True)
        with self.assertRaisesRegex(SwarmError, 'overlaps files'):
            transfer(self.repo, c['id'], b['id'], apply=True)
        self.assertEqual((Path(c['workspace']) / 'shared.txt').read_text(), 'A')
        self.assertEqual(self.readiness(c), 'handoff-required')

    def test_run_is_not_admitted_until_handoff_is_applied(self):
        parent = self.add('API')
        child = self.add('Consumer', [parent['id']], gate='transferred')
        self.mark_parent_completed(parent)
        preview = dispatch(self.repo, max_jobs=1)
        self.assertNotIn(child['id'], preview['ready_in_priority_order'])
        transfer(self.repo, child['id'], parent['id'], apply=True)
        self.assertIn(child['id'], dispatch(self.repo, max_jobs=1)['ready_in_priority_order'])
        with patch('forgequorum.queue.shutil.which', return_value='/fake/codex'), \
             patch('forgequorum.queue.execute_job', return_value={'state': 'completed'}):
            result = dispatch(self.repo, max_jobs=1, execute=True)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['results'][0]['id'], child['id'])

    def test_missing_or_invalid_source_verification_refused(self):
        parent = self.add('API')
        child = self.add('Consumer', [parent['id']], gate='transferred')
        self.mark_parent_completed(parent, verify=False)
        with self.assertRaisesRegex(SwarmError, 'verification'):
            transfer(self.repo, child['id'], parent['id'], apply=True)
        self.assertEqual(self.readiness(child), 'dependency-unverified')

    def test_reject_dirty_target_user_files_before_any_write(self):
        parent = self.add('API')
        child = self.add('Consumer', [parent['id']], gate='transferred')
        self.mark_parent_completed(parent)
        target = Path(child['workspace'])
        (target / 'KEEP.txt').write_text('my local edits', encoding='utf-8')
        with self.assertRaisesRegex(SwarmError, 'unstaged or untracked'):
            transfer(self.repo, child['id'], parent['id'], apply=True)
        self.assertEqual((target / 'KEEP.txt').read_text(), 'my local edits')
        self.assertFalse((target / 'api.txt').exists())

    def test_no_dependency_and_invalid_gate_refused_without_worktree(self):
        with self.assertRaisesRegex(SwarmError, 'Gate'):
            self.add('No parents', gate='transferred')
        with self.assertRaisesRegex(SwarmError, 'Gate'):
            self.add('No parents', gate='invalid')
        parent = self.add('A')
        other = self.add('B')
        with self.assertRaisesRegex(SwarmError, 'list the source'):
            transfer(self.repo, other['id'], parent['id'], apply=True)

    def test_queue_v090_records_migrate_without_gate_field(self):
        parent = self.add('API')
        child = self.add('Tests', [parent['id']])
        _, common = _repo(self.repo)
        with _transaction(common) as (folder, data):
            data['entries'][child['id']].pop('gate')
            data['entries'][child['id']].pop('handoffs')
            _write(folder, data)
        self.mark_parent_completed(parent, verify=False)
        self.assertEqual(self.readiness(child), 'ready')

    def test_cli_reports_gate_and_transfer_preview_without_modifying(self):
        p = self.add('API')
        output = StringIO()
        with redirect_stdout(output):
            code = main(['queue', 'add', 'Implement consumer', '--target', str(self.repo),
                         '--profile', 'go', '--after', p['id'], '--gate', 'transferred'])
        self.assertEqual(code, 0)
        c = json.loads(output.getvalue())
        self.assertEqual(c['gate'], 'transferred')
        self.mark_parent_completed(p)
        output = StringIO()
        with redirect_stdout(output):
            code = main(['queue', 'transfer', c['id'], '--from', p['id'], '--target', str(self.repo)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['state'], 'dry-run')
        self.assertFalse((Path(c['workspace']) / 'api.txt').exists())


    def test_corrupt_gate_metadata_fail_closed(self):
        p = self.add('Parent')
        c = self.add('Dependent', [p['id']])
        _, common = _repo(self.repo)
        file = common / 'forgequorum' / 'queue.json'
        record = json.loads(file.read_text())
        record['entries'][c['id']]['gate'] = []
        file.write_text(json.dumps(record))
        with self.assertRaises(SwarmError):
            snapshot(self.repo)

    def test_parent_symlink_patch_requires_manual_transfer(self):
        p = self.add('Parent')
        c = self.add('Dependent', [p['id']], gate='transferred')
        source = Path(p['workspace'])
        try:
            (source / 'link.txt').symlink_to('not-allowed.txt')
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks unavailable')
        self.git(source, 'add', 'link.txt')
        self.git(source, 'commit', '-qm', 'Add symlink')
        root, common = _repo(self.repo)
        with _transaction(common) as (folder, data):
            data['entries'][p['id']]['state'] = 'completed'
            _write(folder, data)
        job = _load_job(root, common, p['id'])
        job['state'] = 'completed'
        _write_job(common, job)
        with patch('forgequorum.swarm_control.run_verification', return_value={'ok':True, 'results':[{'name':'ok','status':'passed'}]}):
            verify_job(self.repo, p['id'], run=True)
        with self.assertRaisesRegex(SwarmError, 'Symlink'):
            transfer(self.repo, c['id'], p['id'])
        self.assertFalse((Path(c['workspace']) / 'link.txt').exists())

    def test_binary_patch_transfer_stages_without_main_changes(self):
        p = self.add('Source')
        c = self.add('Child', [p['id']], gate='transferred')
        source = Path(p['workspace'])
        (source / 'asset.bin').write_bytes(bytes(range(256)))
        self.git(source, 'add', 'asset.bin')
        self.git(source, 'commit', '-qm', 'Add binary asset')
        root, common = _repo(self.repo)
        with _transaction(common) as (folder, data):
            data['entries'][p['id']]['state'] = 'completed'
            _write(folder, data)
        job = _load_job(root, common, p['id'])
        job['state'] = 'completed'
        _write_job(common, job)
        with patch('forgequorum.swarm_control.run_verification', return_value={'ok':True, 'results':[{'name':'ok','status':'passed'}]}):
            verify_job(self.repo, p['id'], run=True)
        self.assertEqual(transfer(self.repo, c['id'], p['id'], apply=True)['state'], 'staged')
        self.assertEqual((Path(c['workspace']) / 'asset.bin').read_bytes(), bytes(range(256)))
        self.assertFalse((self.repo / 'asset.bin').exists())


if __name__ == '__main__':
    unittest.main()
