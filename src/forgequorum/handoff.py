"""Read-only multi-worktree readiness check; never merges or modifies branches."""
from __future__ import annotations

from pathlib import Path
from .swarm import SwarmError, _repo, _load_job, inspect_job, _git
from .swarm_control import conflicts


def handoff(target: Path, job_ids: list[str]) -> dict:
    if not 2 <= len(job_ids) <= 12 or len(set(job_ids)) != len(job_ids):
        raise SwarmError('Handoff requires 2..12 distinct job IDs')
    root, common = _repo(target)
    collision = conflicts(root, job_ids)
    reasons = []
    jobs = []
    for job_id in job_ids:
        job = _load_job(root, common, job_id)
        current = inspect_job(root, job_id)
        workspace = Path(job['workspace'])
        checks = []
        if current['state'] != 'completed':
            checks.append('job-not-completed')
        if current['changes']:
            checks.append('uncommitted-or-untracked-changes')
        verification = job.get('last_verification')
        if not isinstance(verification, dict) or verification.get('ok') is not True:
            checks.append('missing-or-failed-verification')
        else:
            if verification.get('commit_sha') != current['head_sha']:
                checks.append('verification-for-different-commit')
            if verification.get('dirty') is not False:
                checks.append('verification-on-dirty-worktree')
        if job['base_sha'] != _git(root, 'rev-parse', 'HEAD'):
            checks.append('base-diverged-from-current-head')
        if checks:
            reasons.append({'job_id': job_id, 'blockers': checks})
        jobs.append({'job_id': job_id, 'branch': job['branch'],
                     'head_sha': current['head_sha'], 'blockers': checks})
    if collision['has_overlaps']:
        reasons.append({'issue': 'overlapping-paths', 'details': collision['overlaps']})
    return {
        'ready_for_manual_review': not reasons, 'jobs': jobs,
        'conflicts': collision['overlaps'], 'blockers': reasons,
        'notice': 'This is a conservative preflight only; it does not prove semantic compatibility, run merge-tree, merge branches, publish or deploy.',
    }
