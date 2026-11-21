"""Review-first operational controls for isolated worktree jobs.

No automatic merge, retries, lock deletion, or project-command execution.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess

from .quality import run_verification
from .swarm import (
    SwarmError, ID, _repo, _load_job, _job_dir, _write_job, _registered_workspace,
    _git, _exclusive_run, inspect_job,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _validate_workspace(root: Path, job: dict) -> Path:
    path = Path(job['workspace'])
    if path.is_symlink() or not path.is_dir() or not _registered_workspace(root, path):
        raise SwarmError('Managed worktree is missing or unregistered')
    if _git(path, 'branch', '--show-current') != job['branch']:
        raise SwarmError('Worktree is on an unexpected branch')
    return path


def _lock(common: Path, job_id: str) -> Path:
    path = _job_dir(common) / f'{job_id}.lock'
    if path.is_symlink():
        raise SwarmError('Refusing symlinked run lock')
    return path


def recovery(target: Path, job_id: str, confirm: bool = False) -> dict:
    """Explicitly reclassify a lost worker. Never clear a lock or kill a process."""
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    _validate_workspace(root, job)
    if job['state'] != 'running':
        raise SwarmError('Only a job stuck in running state can be recovered')
    if _lock(common, job_id).exists():
        raise SwarmError('Active or abandoned run lock exists; inspect process and lock manually')
    if not confirm:
        return {'id': job_id, 'state': 'dry-run', 'action': 'mark-interrupted',
                'notice': 'Requires --confirm. First check no Codex or child process is still editing the worktree.'}
    # Claim the lock; prevent another controller from resuming the same job.
    with _exclusive_run(common, job_id):
        job = _load_job(root, common, job_id)
        if job['state'] != 'running':
            raise SwarmError('Job state changed during recovery')
        job['state'] = 'interrupted'
        job['recovery'] = {'at': _now(), 'action': 'operator-marked-interrupted'}
        _write_job(common, job)
    return {'id': job_id, 'state': 'interrupted',
            'notice': 'No retry was attempted; original worktree and all changes are preserved. Inspect before manually restarting work.'}


def request_cancel(target: Path, job_id: str, confirm: bool = False) -> dict:
    """Request cooperative cancellation; the owning worker terminates its child."""
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    _validate_workspace(root, job)
    if job['state'] not in ('running', 'prepared'):
        raise SwarmError('Only prepared or running jobs can be cancelled')
    if not confirm:
        return {'id': job_id, 'state': 'dry-run', 'action': 'cancel',
                'notice': 'Requires --confirm. Running Codex execution will be asked to stop; worktree changes remain.'}
    lock = _lock(common, job_id)
    if job['state'] == 'prepared':
        with _exclusive_run(common, job_id):
            job = _load_job(root, common, job_id)
            if job['state'] != 'prepared':
                raise SwarmError('Job state changed before cancellation')
            job['state'] = 'cancelled'
            job['cancelled_at'] = _now()
            _write_job(common, job)
        return {'id': job_id, 'state': 'cancelled', 'notice': 'No process was launched.'}
    if not lock.is_file():
        raise SwarmError('Running job has no claim lock; inspect process and use recover instead')
    marker = _job_dir(common) / f'{job_id}.cancel'
    if marker.is_symlink():
        raise SwarmError('Refusing symlinked cancellation marker')
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {'id': job_id, 'state': 'cancel-requested', 'notice': 'A cancellation request already exists.'}
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump({'requested_at': _now()}, handle)
    return {'id': job_id, 'state': 'cancel-requested',
            'notice': 'The owning ForgeQuorum process will stop Codex on its next poll; no files are deleted.'}


def _git_paths(worktree: Path, *args: str) -> set[str]:
    # Unlike the generic Git wrapper, preserve leading/trailing whitespace
    # in filenames. Only NUL is a separator.
    try:
        proc = subprocess.run(['git', '-C', str(worktree), *args],
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SwarmError('Cannot read Git changed paths') from error
    if proc.returncode:
        raise SwarmError('Cannot read Git changed paths; inspect repository state')
    return {value for value in proc.stdout.split('\0') if value}


def _paths(root: Path, job: dict) -> set[str]:
    worktree = _validate_workspace(root, job)
    changed = _git_paths(worktree, 'diff', '--name-only', '-z', job['base_sha'], '--')
    untracked = _git_paths(worktree, 'ls-files', '--others', '--exclude-standard', '-z')
    return changed | untracked


def conflicts(target: Path, job_ids: list[str]) -> dict:
    """Read-only collision analysis by path, not automatic semantic merge."""
    if not 2 <= len(job_ids) <= 12 or len(set(job_ids)) != len(job_ids):
        raise SwarmError('Select between 2 and 12 different jobs')
    root, common = _repo(target)
    jobs = {}
    files = {}
    for job_id in job_ids:
        if not ID.fullmatch(job_id):
            raise SwarmError('Invalid job ID')
        jobs[job_id] = _load_job(root, common, job_id)
        files[job_id] = _paths(root, jobs[job_id])
    overlaps = []
    for index, left in enumerate(job_ids):
        for right in job_ids[index + 1:]:
            shared = sorted(files[left] & files[right])
            if shared:
                overlaps.append({'job_a': left, 'job_b': right, 'paths': shared})
    return {'jobs': job_ids, 'overlaps': overlaps, 'has_overlaps': bool(overlaps),
            'file_counts': {job_id: len(files[job_id]) for job_id in job_ids},
            'notice': 'Path overlaps only. No semantic conflicts or Git merge conflicts are proven absent by this check.'}


def verify_job(target: Path, job_id: str, run: bool = False, timeout: int = 120) -> dict:
    """Plan/execute project gates for a specific worktree; run=True is explicit."""
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    workspace = _validate_workspace(root, job)
    if job['state'] == 'running' or _lock(common, job_id).exists():
        raise SwarmError('Cannot verify a worktree while its job is running or locked')
    if not run:
        report = run_verification(workspace, timeout=timeout, run=False)
        report.update({'job_id': job_id, 'state': 'dry-run'})
        return report
    with _exclusive_run(common, job_id):
        job = _load_job(root, common, job_id)
        if job['state'] == 'running':
            raise SwarmError('Job became active while verification was starting')
        report = run_verification(workspace, timeout=timeout, run=True)
        job['last_verification'] = {'at': _now(), 'ok': report['ok'],
                                    'gates': report['results'],
                                    'commit_sha': _git(workspace, 'rev-parse', 'HEAD'),
                                    'dirty': bool(_git(workspace, 'status', '--porcelain'))}
        _write_job(common, job)
    report.update({'job_id': job_id, 'state': 'passed' if report['ok'] else 'failed'})
    return report


def usage_report(target: Path, job_ids: list[str] | None = None) -> dict:
    """Summarize last reported run per job; monetary prices aren't inferred."""
    root, common = _repo(target)
    if job_ids is None or not job_ids:
        directory = _job_dir(common)
        job_ids = sorted(p.stem for p in directory.glob('*.json') if ID.fullmatch(p.stem)) if directory.exists() else []
    if len(job_ids) > 500 or len(set(job_ids)) != len(job_ids):
        raise SwarmError('Usage report allows at most 500 distinct job IDs')
    totals = {'input_tokens': 0, 'cached_input_tokens': 0,
              'output_tokens': 0, 'total_tokens': 0}
    included = []
    unreported = []
    for job_id in job_ids:
        if not ID.fullmatch(job_id):
            raise SwarmError('Invalid job ID')
        job = _load_job(root, common, job_id)
        usage = (job.get('last_execution') or {}).get('usage')
        if not isinstance(usage, dict) or usage.get('source') != 'codex-jsonl':
            unreported.append(job_id)
            continue
        values = {}
        for key in totals:
            value = usage.get(key)
            if type(value) is not int or value < 0:
                raise SwarmError('Invalid recorded usage metadata')
            values[key] = value
        for key, value in values.items():
            totals[key] += value
        included.append({'id': job_id, 'partial': bool(usage.get('partial'))})
    return {'jobs_considered': len(job_ids), 'jobs_with_reported_usage': included,
            'jobs_without_reported_usage': unreported, 'totals': totals,
            'notice': 'Only last-run token counts reported by Codex JSONL; partial or missing data possible. No price, billing estimate, or spending limit.'}
