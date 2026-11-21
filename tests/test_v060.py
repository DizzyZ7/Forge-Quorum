"""Regression coverage for bounded batch execution and Git-only review."""
from __future__ import annotations

import contextlib
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.swarm import (SwarmError, create_job, execute_job,
                               inspect_job, review_job, run_batch)


@unittest.skipUnless(shutil.which("git"), "Git executable is required")
class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Tests")
        self.git("config", "user.email", "qa@example.invalid")
        (self.root / "go.mod").write_text("module example.invalid/app\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def git(self, *args, cwd=None):
        run = subprocess.run(["git", "-C", str(cwd or self.root), *args],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, (args, run.stderr))
        return run.stdout.strip()

    def jobs(self, number):
        return [create_job(self.root, f"Build Go endpoint {i}", "go")
                for i in range(number)]

    def test_preview_is_read_only(self):
        jobs = self.jobs(2)
        with patch("forgequorum.swarm._codex_exec") as model:
            result = run_batch(self.root, [j["id"] for j in jobs])
            model.assert_not_called()
        self.assertEqual(result["state"], "dry-run")
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(all(inspect_job(self.root, j["id"])["state"] == "prepared" for j in jobs))

    def test_invalid_ids_rejected_before_any_execution(self):
        a, b = self.jobs(2)
        for ids in ([a["id"], a["id"]], [a["id"], "../../etc"], [a["id"], "0"*12], []):
            with self.assertRaises(SwarmError):
                run_batch(self.root, ids, execute=True)
        self.assertEqual(inspect_job(self.root, a["id"])["state"], "prepared")

    def test_concurrency_and_order(self):
        jobs = self.jobs(4)
        active, peak = 0, 0
        mutex = threading.Lock()
        def fake(*args):
            nonlocal active, peak
            with mutex:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with mutex:
                active -= 1
            return "completed", 0, 2
        with patch("forgequorum.swarm.shutil.which", return_value="/fake/codex"), \
             patch("forgequorum.swarm._codex_exec", side_effect=fake):
            result = run_batch(self.root, [j["id"] for j in jobs], max_parallel=2, execute=True)
        self.assertEqual(result["state"], "completed")
        self.assertEqual([x["id"] for x in result["jobs"]], [j["id"] for j in jobs])
        self.assertEqual(peak, 2)
        self.assertEqual(result["completed"], 4)
        self.assertTrue(all("elapsed_seconds" in x["last_execution"] for x in result["jobs"]))

    def test_cap_and_timeout_validation(self):
        j = self.jobs(1)[0]
        for n in (0, 5):
            with self.assertRaisesRegex(SwarmError, "max_parallel"):
                run_batch(self.root, [j["id"]], max_parallel=n)
        for n in (0, 29, 3601):
            with self.assertRaisesRegex(SwarmError, "timeout"):
                run_batch(self.root, [j["id"]], timeout=n)

    def test_lock_prevents_overlapping_execution(self):
        j = self.jobs(1)[0]
        def fake(*args):
            with self.assertRaisesRegex(SwarmError, "claimed|not runnable"):
                execute_job(self.root, j["id"], execute=True)
            return "completed", 0, 1
        with patch("forgequorum.swarm.shutil.which", return_value="/fake/codex"), \
             patch("forgequorum.swarm._codex_exec", side_effect=fake):
            result = execute_job(self.root, j["id"], execute=True)
        self.assertEqual(result["state"], "completed")
        lock = self.root / ".git" / "forgequorum" / "jobs" / f"{j['id']}.lock"
        self.assertFalse(lock.exists())
        pending = self.jobs(1)[0]
        lock = self.root / ".git" / "forgequorum" / "jobs" / f"{pending['id']}.lock"
        lock.write_text("abandoned lock")
        with self.assertRaisesRegex(SwarmError, "claimed"):
            run_batch(self.root, [pending["id"]])
        self.assertTrue(lock.exists())

    def test_partial_failure_preserves_every_workspace(self):
        jobs = self.jobs(3)
        def fake(workspace, prompt, timeout):
            return ("failed", 17, 2) if Path(workspace) == Path(jobs[1]["workspace"]) else ("completed", 0, 1)
        with patch("forgequorum.swarm.shutil.which", return_value="/fake/codex"), \
             patch("forgequorum.swarm._codex_exec", side_effect=fake):
            result = run_batch(self.root, [j["id"] for j in jobs], execute=True)
        self.assertEqual(result["state"], "partial-failure")
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["jobs"][1]["last_execution"]["exit_code"], 17)
        self.assertTrue(all(Path(j["workspace"]).exists() for j in jobs))

    def test_unexpected_worker_exception_is_redacted(self):
        jobs = self.jobs(2)
        def fake(workspace, prompt, timeout):
            if Path(workspace) == Path(jobs[0]["workspace"]):
                raise RuntimeError("A SENSITIVE TOKEN")
            return "completed", 0, 1
        with patch("forgequorum.swarm.shutil.which", return_value="/fake/codex"), \
             patch("forgequorum.swarm._codex_exec", side_effect=fake):
            result = run_batch(self.root, [j["id"] for j in jobs], execute=True)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["state"], "partial-failure")
        self.assertNotIn("SENSITIVE", json.dumps(result))

    def test_review_is_read_only_and_unverified(self):
        j = self.jobs(1)[0]
        worktree = Path(j["workspace"])
        (worktree / "go.mod").write_text("module example.invalid/revised\n")
        (worktree / "notes.txt").write_text("untracked private contents")
        summary = review_job(self.root, j["id"])
        self.assertEqual(summary["verification"], "unverified")
        self.assertEqual(summary["modified_entries"], 2)
        self.assertIn("go.mod", summary["tracked_diff_summary"])
        self.assertIn("notes.txt", str(summary["files"]))
        self.assertNotIn("untracked private contents", json.dumps(summary))

    def test_changed_branch_refuses_model_execution(self):
        j = self.jobs(1)[0]
        self.git("switch", "-q", "-c", "unrelated", cwd=j["workspace"])
        with patch("forgequorum.swarm._codex_exec") as model:
            with self.assertRaisesRegex(SwarmError, "branch"):
                execute_job(self.root, j["id"], execute=True)
            model.assert_not_called()

    def test_cli_review_and_batch(self):
        j = self.jobs(1)[0]
        buffer = StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["swarm", "batch", j["id"], "--target", str(self.root), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["state"], "dry-run")
        buffer = StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["swarm", "review", j["id"], "--target", str(self.root), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["id"], j["id"])


if __name__ == "__main__":
    unittest.main()
