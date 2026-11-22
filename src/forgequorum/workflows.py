"""Validated declarative work plans; no automatic AI invocation or code integration.

Apply creates isolated queue jobs sequentially. On partial failure it never
removes worktrees or resets source files; it reports concrete IDs for recovery.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from .profiles import profile_names
from .queue import MAX_ENTRIES, _read, enqueue
from .swarm import SwarmError, MAX_TASK, _repo, _job_dir

MAX_STEPS = 12
MAX_RECIPE_BYTES = 64 * 1024
KEY = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')


class PartialWorkflowError(SwarmError):
    def __init__(self, message: str, created: dict[str, str]):
        super().__init__(message)
        self.created = created


def _parse(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        raise SwarmError('Recipe must be a regular, non-symlinked JSON file')
    try:
        if path.stat().st_size > MAX_RECIPE_BYTES:
            raise SwarmError('Recipe exceeds 64 KiB')
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SwarmError('Recipe must contain valid UTF-8 JSON') from exc
    if not isinstance(data, dict) or set(data) != {'schema', 'steps'} or type(data['schema']) is not int or data['schema'] != 1:
        raise SwarmError('Recipe requires schema: 1 and steps')
    steps = data['steps']
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise SwarmError(f'Recipe must contain 1 to {MAX_STEPS} steps')
    normalized: list[dict] = []
    seen: set[str] = set()
    for raw in steps:
        if not isinstance(raw, dict) or not {'key', 'task'} <= set(raw) or set(raw) - {'key', 'task', 'after', 'profile', 'priority', 'gate', 'max_agents'}:
            raise SwarmError('Unknown or missing recipe step fields')
        key, task = raw['key'], raw['task']
        after = raw.get('after', [])
        profile = raw.get('profile', 'auto')
        priority = raw.get('priority', 0)
        gate = raw.get('gate', 'order')
        max_agents = raw.get('max_agents', 3)
        if not isinstance(key, str) or KEY.fullmatch(key) is None or key in seen:
            raise SwarmError('Every step must have a unique lowercase key')
        if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK:
            raise SwarmError(f'Invalid task description for {key}')
        if not isinstance(profile, str) or profile not in ('auto', *profile_names()):
            raise SwarmError(f'Invalid profile for {key}')
        if type(priority) is not int or not -100 <= priority <= 100:
            raise SwarmError(f'Invalid priority for {key}')
        if type(max_agents) is not int or not 1 <= max_agents <= 6:
            raise SwarmError(f'Invalid max_agents for {key}')
        if not isinstance(gate, str) or gate not in ('order', 'verified', 'transferred'):
            raise SwarmError(f'Invalid gate for {key}')
        if (not isinstance(after, list) or len(after) > MAX_STEPS
                or any(not isinstance(dep, str) or dep not in seen for dep in after)
                or len(set(after)) != len(after) or (gate != 'order' and not after)):
            raise SwarmError(f'{key}: dependencies must reference earlier steps; strict gates require dependencies')
        seen.add(key)
        normalized.append({'key': key, 'task': task, 'after': after, 'profile': profile,
                           'priority': priority, 'gate': gate, 'max_agents': max_agents})
    return normalized


def workflow(target: Path, recipe: Path, apply: bool = False) -> dict:
    """Read-only preview unless explicitly authorized; never launches Codex."""
    steps = _parse(recipe)
    root, common = _repo(target)
    # Read-only on preview; do not create a queue lock or metadata directory.
    folder = _job_dir(common).parent
    if folder.is_symlink():
        raise SwarmError('Refusing symlinked queue directory')
    existing = _read(folder)
    if len(existing['entries']) + len(steps) > MAX_ENTRIES:
        raise SwarmError('Not enough room in the queue for this workflow')
    public = [{key: step[key] for key in ('key', 'after', 'profile', 'priority', 'gate', 'max_agents')}
              for step in steps]
    if not apply:
        return {'state': 'dry-run', 'execution_authorized': False, 'steps': public,
                'count': len(public), 'notice': 'No worktrees or Codex processes created. --apply queues the worktrees only.'}
    created: dict[str, str] = {}
    try:
        for step in steps:
            depends = [created[name] for name in step['after']]
            result = enqueue(root, step['task'], priority=step['priority'], after=depends,
                             profile=step['profile'], max_agents=step['max_agents'], gate=step['gate'])
            created[step['key']] = result['id']
    except (SwarmError, OSError, ValueError) as exc:
        raise PartialWorkflowError('Workflow could not finish creating all jobs; existing worktrees preserved. '
                                   f'Created IDs: {json.dumps(created, sort_keys=True)}. Cause: {exc}', created) from exc
    return {'state': 'queued', 'execution_authorized': False, 'count': len(created),
            'job_ids': created, 'steps': public,
            'notice': 'Only queued worktrees were created. Execute with `fq queue run --execute` after review.'}
