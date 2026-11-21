"""Scheduler admission, conservative reservations and manual-merge preflight."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from forgequorum.scheduler import (claim, configure, release, settle, status, MAX_PARALLEL)
from forgequorum.swarm import (SwarmError, create_job, execute_job, inspect_job, _write_job,
                               run_batch)
from forgequorum.handoff import handoff


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        env = patch.dict(os.environ, FORGEQUORUM_STATE_DIR=str(self.directory / 'scheduler'))
        env.start()
        self.addCleanup(env.stop)

    def test_fresh_defaults_and_config_requires_confirm(self):
        self.assertEqual(status()['max_running'], 2)
        self.assertEqual(configure(3, 1000)['state'], 'dry-run')
        self.assertEqual(status()['max_running'], 2)
        self.assertEqual(configure(3, 1000, confirm=True)['state'], 'configured')
        self.assertEqual(status()['daily_token_limit'], 1000)

    def test_global_slots_and_release(self):
        first = claim('example/repo','first')
        second = claim('example/repo','second')
        with self.assertRaisesRegex(SwarmError, 'concurrent'):
            claim('example/repo', 'third')
        self.assertEqual(status()['active_count'], 2)
        settle(first)
        third = claim('example/repo', 'third')
        self.assertEqual(status()['active_count'], 2)
        settle(second)
        settle(third)
        self.assertEqual(status()['active_count'], 0)

    def test_prevents_duplicate_job_claim(self):
        first = claim('example/repo', 'same')
        with self.assertRaisesRegex(SwarmError, 'already'):
            claim('example/repo', 'same')
        settle(first)

    def test_daily_reservations_fail_closed(self):
        configure(3, 100, True)
        with self.assertRaisesRegex(SwarmError, 'reserve-tokens'):
            claim('repo', 'one')
        ticket = claim('repo', 'one', 75)
        with self.assertRaisesRegex(SwarmError, 'budget exhausted'):
            claim('repo', 'two', 26)
        # Missing telemetry must not refund reserved tokens.
        settle(ticket)
        self.assertEqual(status()['charged_tokens_today'],75)
        with self.assertRaisesRegex(SwarmError, 'budget exhausted'):
            claim('repo','three',26)

    def test_reported_amount_replaces_reservation_and_can_exceed(self):
        configure(2,100,True)
        t = claim('repo','one',70)
        settle(t, reported_tokens=90)
        self.assertEqual(status()['charged_tokens_today'],90)
        with self.assertRaisesRegex(SwarmError, 'budget exhausted'):
            claim('repo','second',11)
        t=claim('repo','second',10)
        settle(t,reported_tokens=30)
        self.assertEqual(status()['charged_tokens_today'],120)

    def test_reported_reduces_charge(self):
        configure(2,100,True)
        t=claim('repo','first',80)
        settle(t,reported_tokens=25)
        self.assertEqual(status()['charged_tokens_today'],25)
        t2=claim('repo','second',75)
        settle(t2,reported_tokens=0)
        self.assertEqual(status()['charged_tokens_today'],25)

    def test_config_refuses_during_active_work(self):
        t=claim('repo','one')
        with self.assertRaisesRegex(SwarmError, 'while jobs'):
            configure(3,200,True)
        self.assertEqual(status()['max_running'],2)
        settle(t)

    def test_invalid_inputs_and_symlink_storage(self):
        for n in (-1, MAX_PARALLEL + 1):
            with self.assertRaises(SwarmError):
                configure(n,0,True)
        for n in (-1, 10**13):
            with self.assertRaises(SwarmError):
                claim('repo','x',reserve_tokens=n)
        with self.assertRaises(SwarmError):
            claim('repo','x',wait_seconds=301)
        with patch.dict(os.environ, FORGEQUORUM_STATE_DIR='relative/state'):
            with self.assertRaisesRegex(SwarmError, 'absolute'):
                status()

    def test_release_requires_dead_pid_and_confirmation(self):
        ticket=claim('repo','one',200)
        self.assertEqual(release(ticket)['state'],'dry-run')
        with self.assertRaisesRegex(SwarmError, 'still present'):
            release(ticket,True)
        settle(ticket)
        with self.assertRaisesRegex(SwarmError, 'Unknown'):
            release(ticket,True)

    def test_manual_recovery_keeps_conservative_charge(self):
        configure(2,100,True)
        ticket=claim('repo','orphan',60)
        path=self.directory/'scheduler'/'state.json'
        state=json.loads(path.read_text())
        state['active'][ticket]['pid']=999999999
        path.write_text(json.dumps(state))
        self.assertEqual(release(ticket,True)['state'],'released')
        self.assertEqual(status()['charged_tokens_today'],60)

    def test_exclusive_mutex_blocks_after_timeout(self):
        d=self.directory/'scheduler'
        d.mkdir(exist_ok=True)
        (d/'.mutex').mkdir()
        with patch('forgequorum.scheduler.monotonic',side_effect=[0,4]):
            with self.assertRaisesRegex(SwarmError, 'locked|busy|abandoned'):
                status()
        self.assertTrue((d/'.mutex').exists())

    def test_another_process_observes_global_claim(self):
        configure(1,0,True)
        ticket=claim('repo','first')
        child = subprocess.run(
            [sys.executable,'-c','from forgequorum.scheduler import claim; claim("repo", "second")'],
            capture_output=True, text=True, timeout=15,
            env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]/'src')})
        self.assertNotEqual(child.returncode,0)
        self.assertIn('Global concurrent Codex', child.stderr)
        settle(ticket)


@unittest.skipUnless(shutil.which('git'), 'Git required')
class IntegrationTests(SchedulerTests):
    def setUp(self):
        super().setUp()
        self.repo=self.directory/'repo'
        self.repo.mkdir()
        self.git('init','-q','-b','main')
        self.git('config','user.name','QA')
        self.git('config','user.email','ci@example.invalid')
        (self.repo/'go.mod').write_text('module example.invalid/test\n')
        self.git('add','.')
        self.git('commit','-qm','Initial')

    def git(self,*cmd,repo=None):
        completed=subprocess.run(['git','-C',str(repo or self.repo),*cmd],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,(cmd,completed.stderr))
        return completed.stdout.strip()

    def job(self):
        return create_job(self.repo,'Make a reliable service',profile='go')

    def test_execute_charges_usage_and_clears_global_slot(self):
        configure(1, 100, True)
        j=self.job()
        usage={'source':'codex-jsonl','input_tokens':30,'cached_input_tokens':0,
               'output_tokens':12,'total_tokens':42,'partial':False}
        with patch('forgequorum.swarm.shutil.which',return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec',return_value=('completed',0,2,usage)):
            outcome=execute_job(self.repo,j['id'],execute=True,reserve_tokens=70)
        self.assertEqual(outcome['state'],'completed')
        self.assertEqual(status()['charged_tokens_today'],42)
        self.assertEqual(status()['active_count'],0)

    def test_quota_denial_does_not_launch_codex(self):
        configure(1, 5, True)
        j=self.job()
        with patch('forgequorum.swarm.shutil.which',return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec') as executor:
            with self.assertRaisesRegex(SwarmError,'budget exhausted'):
                execute_job(self.repo,j['id'],execute=True,reserve_tokens=10)
            executor.assert_not_called()
        self.assertEqual(inspect_job(self.repo,j['id'])['state'],'prepared')
        self.assertEqual(status()['active_count'],0)

    def test_batch_queues_when_global_limit_is_one(self):
        configure(1,0,True)
        jobs=[self.job() for _ in range(3)]
        active=0
        peak=0
        lock=threading.Lock()
        def fake(*args):
            nonlocal active,peak
            with lock:
                active+=1
                peak=max(active,peak)
            time.sleep(0.05)
            with lock: active-=1
            return ('completed',0,2)
        with patch('forgequorum.swarm.shutil.which',return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec',side_effect=fake):
            outcome=run_batch(self.repo,[j['id'] for j in jobs],max_parallel=3,
                              execute=True,wait_seconds=5)
        self.assertEqual(outcome['completed'],3)
        self.assertEqual(peak,1)

    def test_handoff_requires_verified_committed_results(self):
        jobs=[self.job() for _ in range(2)]
        with patch('forgequorum.swarm.shutil.which',return_value='/fake/codex'), \
             patch('forgequorum.swarm._codex_exec',return_value=('completed',0,1)):
            for job in jobs:
                execute_job(self.repo,job['id'],execute=True)
        report=handoff(self.repo,[j['id'] for j in jobs])
        self.assertFalse(report['ready_for_manual_review'])
        self.assertIn('missing-or-failed-verification',report['jobs'][0]['blockers'])
        for job in jobs:
            info=inspect_job(self.repo,job['id'])
            info['last_verification']={'ok':True,'commit_sha':info['head_sha'],'dirty':False}
            _write_job(self.repo/'.git',info)
        self.assertTrue(handoff(self.repo,[j['id'] for j in jobs])['ready_for_manual_review'])

    def test_handoff_rejects_overlaps_without_modifying_workspaces(self):
        jobs=[self.job() for _ in range(2)]
        for j in jobs:
            (Path(j['workspace'])/'go.mod').write_text('changed')
        result=handoff(self.repo,[j['id'] for j in jobs])
        self.assertFalse(result['ready_for_manual_review'])
        self.assertEqual(result['conflicts'][0]['paths'],['go.mod'])
        self.assertTrue(all((Path(j['workspace'])/'go.mod').read_text()=='changed' for j in jobs))


if __name__=='__main__':
    unittest.main()
