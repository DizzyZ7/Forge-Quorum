"""Crash-conservative, repository-scoped queue for opt-in Codex worktree jobs.

Dependencies order execution only. No worktree content is copied, merged or deployed.
The directory mutex serializes queue selection across independent CLI processes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
import os
from pathlib import Path
import shutil
import tempfile
from time import monotonic, sleep
from uuid import uuid4

from .swarm import (ID, SwarmError, _repo, _job_dir, _load_job,
                    _check_runnable, create_job, execute_job)
from .scheduler import _pid_alive

SCHEMA = 1
MAX_ENTRIES = 500
MAX_BATCH = 12
MAX_PARALLEL = 4
MAX_PRIORITY = 100
MAX_EVENTS = 500
EVENT_KINDS = {"queued", "claimed", "completed", "failed", "cancelled", "reprioritized", "retried", "recovered", "transferred"}
STATES = {'queued', 'claimed', 'completed', 'failed', 'cancelled'}
GATES = {'order', 'verified', 'transferred'}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _directory(common: Path) -> Path:
    folder = _job_dir(common).parent
    if folder.is_symlink():
        raise SwarmError('Refusing symlinked queue directory')
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _validate(data: object) -> dict:
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('entries'), dict):
        raise SwarmError('Invalid queue metadata; refusing execution')
    entries = data['entries']
    events = data.get('events', [])
    if (not isinstance(events, list) or len(events) > MAX_EVENTS or any(
        not isinstance(e, dict) or set(e) != {'at', 'job_id', 'kind'}
        or not isinstance(e['at'], str) or len(e['at']) > 40
        or not isinstance(e['job_id'], str) or ID.fullmatch(e['job_id']) is None
        or not isinstance(e.get('kind'), str) or e['kind'] not in EVENT_KINDS for e in events
    )):
        raise SwarmError('Invalid queue event history; refusing execution')
    if len(entries) > MAX_ENTRIES:
        raise SwarmError('Queue capacity exceeded')
    for key, item in entries.items():
        if (not isinstance(key, str) or ID.fullmatch(key) is None or not isinstance(item, dict)
                or item.get('id') != key or not isinstance(item.get('state'), str) or item['state'] not in STATES
                or type(item.get('priority')) is not int or not -MAX_PRIORITY <= item['priority'] <= MAX_PRIORITY
                or type(item.get('sequence')) is not int or item['sequence'] < 0
                or not isinstance(item.get('gate', 'order'), str)
                or item.get('gate', 'order') not in GATES
                or not isinstance(item.get('after'), list)
                or len(item['after']) > MAX_BATCH or len(set(map(str, item['after']))) != len(item['after'])
                or any(not isinstance(x, str) or ID.fullmatch(x) is None or x == key for x in item['after'])):
            raise SwarmError('Invalid queue entry; refusing execution')
        handoffs = item.get('handoffs', {})
        if not isinstance(handoffs, dict) or len(handoffs) > MAX_BATCH or any(key not in item['after'] for key in handoffs):
            raise SwarmError('Invalid dependency transfer provenance')
        seen_sequences = set()
        for key, record in handoffs.items():
            if (not isinstance(record, dict)
                    or type(record.get('sequence')) is not int
                    or not 1 <= record['sequence'] <= MAX_BATCH
                    or record['sequence'] in seen_sequences
                    or any(not isinstance(record.get(field), str)
                           or re.fullmatch(r'[0-9a-f]{40,64}', record[field]) is None
                           for field in ('source_sha', 'destination_sha'))
                    or any(not isinstance(record.get(field), str)
                           or re.fullmatch(r'[0-9a-f]{64}', record[field]) is None
                           for field in ('patch_sha256', 'index_sha256'))
                    or not isinstance(record.get('paths'), list)
                    or len(record['paths']) > 1000
                    or any(not isinstance(name, str) or not name or '\0' in name
                           or name.startswith('/') or '..' in name.split('/')
                           for name in record['paths'])
                    or len(set(record['paths'])) != len(record['paths'])):
                raise SwarmError('Invalid dependency transfer record')
            seen_sequences.add(record['sequence'])
        if item['state'] == 'claimed':
            claim = item.get('claim')
            if (not isinstance(claim, dict) or type(claim.get('pid')) is not int
                    or claim['pid'] <= 0 or not isinstance(claim.get('nonce'), str)
                    or len(claim['nonce']) != 32):
                raise SwarmError('Invalid queue claim')
        elif item.get('claim') is not None:
            raise SwarmError('Unexpected queue claim')
    if len({item['sequence'] for item in entries.values()}) != len(entries):
        raise SwarmError('Duplicate queue sequence')
    for item in entries.values():
        if any(dep not in entries for dep in item['after']):
            raise SwarmError('Queue has a missing dependency')
        if any(entries[dep]['sequence'] >= item['sequence'] for dep in item['after']):
            raise SwarmError('Queue dependency order is invalid')
    return data


def _read(folder: Path) -> dict:
    file = folder / 'queue.json'
    if file.is_symlink():
        raise SwarmError('Refusing symlinked queue metadata')
    if not file.exists():
        return {'schema': SCHEMA, 'entries': {}, 'events': []}
    try:
        return _validate(json.loads(file.read_text(encoding='utf-8')))
    except (ValueError, OSError, UnicodeError) as exc:
        raise SwarmError('Queue metadata is unreadable') from exc


def _event(data: dict, kind: str, job_id: str) -> None:
    """Append bounded, task-content-free events to the same atomic queue snapshot."""
    if kind not in EVENT_KINDS or ID.fullmatch(job_id) is None:
        raise SwarmError('Invalid event')
    data['events'] = (data.get('events', []) + [{'at': _now(), 'job_id': job_id, 'kind': kind}])[-MAX_EVENTS:]


def events(target: Path, limit: int = 30) -> dict:
    if type(limit) is not int or not 1 <= limit <= MAX_EVENTS:
        raise SwarmError(f'Event limit must be between 1 and {MAX_EVENTS}')
    _, common = _repo(target)
    # Reads without creating queue storage in a pristine repository.
    folder = _job_dir(common).parent
    if folder.is_symlink():
        raise SwarmError('Refusing symlinked event directory')
    data = _read(folder)
    return {'events': data.get('events', [])[-limit:],
            'returned': min(limit, len(data.get('events', []))),
            'retained': len(data.get('events', [])),
            'notice': 'Bounded local queue transitions only; no prompts, transcripts or model payloads.'}


def dashboard(target: Path) -> dict:
    """Read-only, deterministic UI projection. Never inspects agent transcripts."""
    info = snapshot(target)
    counts: dict[str, int] = {}
    blocked: dict[str, int] = {}
    for item in info['items']:
        counts[item['state']] = counts.get(item['state'], 0) + 1
        if item['state'] == 'queued' and item['readiness'] != 'ready':
            blocked[item['readiness']] = blocked.get(item['readiness'], 0) + 1
    return {'total': info['total'], 'ready': info['ready'],
            'states': counts, 'blocked_reasons': blocked, 'items': info['items'],
            'notice': 'Local metadata snapshot; not a proof of successful code quality, cost or remote execution.'}


def _write(folder: Path, data: dict) -> None:
    _validate(data)
    file = folder / 'queue.json'
    if file.is_symlink():
        raise SwarmError('Refusing symlinked queue metadata')
    fd, temp = tempfile.mkstemp(prefix='.fq-queue-', dir=folder)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            os.chmod(temp, 0o600)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temp, file)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def _transaction(common: Path):
    folder = _directory(common)
    lock = folder / '.queue-mutex'
    if lock.is_symlink():
        raise SwarmError('Refusing symlinked queue lock')
    deadline = monotonic() + 3
    while True:
        try:
            lock.mkdir(mode=0o700)
            break
        except FileExistsError as exc:
            if monotonic() >= deadline:
                raise SwarmError('Queue mutex is busy or abandoned; inspect before manual recovery') from exc
            sleep(0.025)
    try:
        yield folder, _read(folder)
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def _order(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda x: (-x['priority'], x['sequence'], x['id']))


def _reason(item: dict, entries: dict, root: Path | None = None, common: Path | None = None) -> str:
    if item['state'] != 'queued':
        return item['state']
    if any(entries[dep]['state'] in ('failed', 'cancelled') for dep in item['after']):
        return 'dependency-failed'
    if any(entries[dep]['state'] != 'completed' for dep in item['after']):
        return 'waiting-for-dependencies'
    if item.get('gate', 'order') != 'order':
        if root is None or common is None:
            return 'dependency-unverified'
        from .transfer import dependency_readiness
        return dependency_readiness(root, common, item, entries)
    return 'ready'


def enqueue(target: Path, task: str, priority: int = 0, after: list[str] | None = None,
            profile: str = 'auto', max_agents: int = 3, gate: str = 'order') -> dict:
    """Create a reviewable worktree and enqueue it; never invoke Codex."""
    if type(priority) is not int or not -MAX_PRIORITY <= priority <= MAX_PRIORITY:
        raise SwarmError('priority must be between -100 and 100')
    after = after or []
    if not isinstance(gate, str) or gate not in GATES or (gate != 'order' and not after):
        raise SwarmError('Gate must be order, verified or transferred; strict gates require dependencies')
    if (len(after) > MAX_BATCH or len(set(after)) != len(after)
            or any(not isinstance(x, str) or ID.fullmatch(x) is None for x in after)):
        raise SwarmError('Specify up to 12 unique valid dependency job IDs')
    root, common = _repo(target)
    # Perform preflight before creating an isolated worktree.
    with _transaction(common) as (_, data):
        if len(data['entries']) >= MAX_ENTRIES:
            raise SwarmError('Queue is full; preserve existing jobs and archive manually')
        if any(x not in data['entries'] for x in after):
            raise SwarmError('Dependencies must already exist in this repository queue')
    job = create_job(root, task, profile, max_agents)
    try:
        with _transaction(common) as (folder, data):
            if len(data['entries']) >= MAX_ENTRIES or any(x not in data['entries'] for x in after):
                raise SwarmError('Queue changed while preparing the worktree')
            sequence = max((e['sequence'] for e in data['entries'].values()), default=0) + 1
            record = {'id': job['id'], 'priority': priority, 'after': after,
                      'sequence': sequence, 'state': 'queued', 'gate': gate, 'handoffs': {}, 'created_at': _now(),
                      'claim': None, 'last_result': None}
            data['entries'][job['id']] = record
            _event(data, 'queued', job['id'])
            _write(folder, data)
    except Exception as exc:
        raise SwarmError(f'Worktree {job["id"]} was created but queue registration failed; inspect it manually') from exc
    return {'id': job['id'], 'state': 'queued', 'priority': priority, 'after': after, 'gate': gate,
            'workspace': job['workspace'], 'notice': 'Execution order only. Dependencies do not transfer code between worktrees.'}


def snapshot(target: Path) -> dict:
    root, common = _repo(target)
    with _transaction(common) as (_, data):
        entries = data['entries']
        ordered = _order(list(entries.values()))
        items = [{'id': x['id'], 'state': x['state'], 'readiness': _reason(x, entries, root, common),
                  'priority': x['priority'], 'after': x['after'], 'gate': x.get('gate', 'order'),
                  'transferred_from': sorted(x.get('handoffs', {})), 'sequence': x['sequence'],
                  'created_at': x['created_at'], 'claimed_at': x.get('claimed_at')}
                 for x in ordered]
    return {'total': len(items), 'ready': sum(x['readiness'] == 'ready' for x in items),
            'items': items, 'notice': 'Dependencies control run order only, not code integration. Claims after a crash require operator recovery.'}


def reprioritize(target: Path, job_id: str, priority: int, confirm: bool = False) -> dict:
    if type(priority) is not int or not -MAX_PRIORITY <= priority <= MAX_PRIORITY:
        raise SwarmError('priority must be between -100 and 100')
    if not ID.fullmatch(job_id):
        raise SwarmError('Invalid job ID')
    _, common = _repo(target)
    with _transaction(common) as (folder, data):
        item = data['entries'].get(job_id)
        if item is None:
            raise SwarmError('Unknown queued job')
        if item['state'] != 'queued':
            raise SwarmError('Only a queued job can change priority')
        if confirm:
            item['priority'] = priority
            _event(data, 'reprioritized', job_id)
            _write(folder, data)
    return {'id': job_id, 'priority': priority, 'state': 'updated' if confirm else 'dry-run'}


def _claim_next(root: Path, common: Path) -> tuple[str, str] | None:
    with _transaction(common) as (folder, data):
        entries = data['entries']
        available = _order([x for x in entries.values() if _reason(x, entries, root, common) == 'ready'])
        if not available:
            return None
        item = available[0]
        claim = uuid4().hex
        item.update(state='claimed', claim={'pid': os.getpid(), 'nonce': claim}, claimed_at=_now())
        _event(data, 'claimed', item['id'])
        _write(folder, data)
        return item['id'], claim


def _finish(common: Path, job_id: str, nonce: str, state: str, error: str | None = None) -> None:
    with _transaction(common) as (folder, data):
        item = data['entries'].get(job_id)
        if (item is None or item['state'] != 'claimed' or item['claim']['nonce'] != nonce
                or item['claim']['pid'] != os.getpid()):
            raise SwarmError('Queue claim changed; refusing to overwrite another worker state')
        item['state'] = state
        item['claim'] = None
        item['finished_at'] = _now()
        item['last_result'] = {'state': state, 'error': error}
        _event(data, state, job_id)
        _write(folder, data)


def dispatch(target: Path, max_jobs: int = 1, parallel: int = 1,
             timeout: int = 900, reserve_tokens: int = 0,
             wait_seconds: int = 0, execute: bool = False) -> dict:
    if (type(max_jobs) is not int or not 1 <= max_jobs <= MAX_BATCH
            or type(parallel) is not int or not 1 <= parallel <= MAX_PARALLEL
            or type(timeout) is not int or not 30 <= timeout <= 3600
            or type(wait_seconds) is not int or not 0 <= wait_seconds <= 300
            or type(reserve_tokens) is not int or not 0 <= reserve_tokens <= 10**12):
        raise SwarmError('Invalid queue run limits')
    root, common = _repo(target)
    if not execute:
        info = snapshot(root)
        ready = [x['id'] for x in info['items'] if x['readiness'] == 'ready']
        return {'state': 'dry-run', 'execution_authorized': False, 'ready_in_priority_order': ready[:max_jobs],
                'ready_total': len(ready), 'parallel': parallel, 'max_jobs': max_jobs,
                'notice': 'Run with --execute to call Codex. Jobs only use committed snapshots, not dependent worktree changes.'}
    if not shutil.which('codex'):
        raise SwarmError('Codex CLI missing from PATH; no queue entries claimed')

    def worker(jid: str, nonce: str) -> dict:
        try:
            _check_runnable(root, common, jid)
            info = execute_job(root, jid, timeout=timeout, execute=True,
                               reserve_tokens=reserve_tokens, wait_seconds=wait_seconds)
            state = 'completed' if info['state'] == 'completed' else 'failed'
            result = {'id': jid, 'state': state, 'codex_state': info['state']}
        except (SwarmError, OSError, ValueError) as exc:
            state = 'failed'
            result = {'id': jid, 'state': state, 'error': str(exc)}
        except Exception as exc:
            state = 'failed'
            result = {'id': jid, 'state': state, 'error': f'Worker error: {type(exc).__name__}'}
        _finish(common, jid, nonce, state, result.get('error'))
        return result

    submitted = 0
    results = []
    active = set()
    with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix='fq-queue') as executor:
        while submitted < max_jobs or active:
            while submitted < max_jobs and len(active) < parallel:
                claimed = _claim_next(root, common)
                if claimed is None:
                    break
                active.add(executor.submit(worker, *claimed))
                submitted += 1
            if not active:
                break
            done, active = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                results.append(future.result())
    state = 'completed' if results and all(x['state'] == 'completed' for x in results) else 'partial-failure' if results else 'nothing-ready'
    return {'state': state, 'execution_authorized': True, 'jobs_started': submitted,
            'results': results, 'notice': 'No code merged or published; inspect and verify worktrees independently.'}



def cancel_queued(target: Path, job_id: str, confirm: bool = False) -> dict:
    """Cancel admission for a queued job only; leave its worktree untouched."""
    if not ID.fullmatch(job_id):
        raise SwarmError('Invalid job ID')
    _, common = _repo(target)
    with _transaction(common) as (folder, data):
        entry = data['entries'].get(job_id)
        if entry is None or entry['state'] != 'queued':
            raise SwarmError('Only queued jobs can be cancelled here; use swarm cancel for running jobs')
        if confirm:
            entry['state'] = 'cancelled'
            entry['finished_at'] = _now()
            entry['last_result'] = {'state': 'cancelled', 'error': None}
            _event(data, 'cancelled', job_id)
            _write(folder, data)
    return {'id': job_id, 'state': 'cancelled' if confirm else 'dry-run',
            'notice': 'Queue admission cancelled; Git branch and worktree are preserved.'}


def observe(target: Path, seconds: float = 20, interval: float = 1):
    """Yield changing queue snapshots for up to 300 seconds (no daemon or model calls)."""
    if (not isinstance(seconds, (float, int)) or type(seconds) is bool or not 0 < seconds <= 300
            or not isinstance(interval, (float, int)) or type(interval) is bool
            or not 0.1 <= interval <= 30):
        raise SwarmError('Watch duration must be (0, 300] and interval [0.1, 30] seconds')
    deadline = monotonic() + seconds
    previous = None
    while True:
        result = snapshot(target)
        state = [(item['id'], item['state'], item['readiness'], item['priority'])
                 for item in result['items']]
        if state != previous:
            yield {'observed_at': _now(), 'total': result['total'], 'ready': result['ready'],
                   'items': result['items']}
            previous = state
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(interval, remaining))


def requeue(target: Path, job_id: str, confirm: bool = False) -> dict:
    if not ID.fullmatch(job_id):
        raise SwarmError('Invalid job ID')
    root, common = _repo(target)
    with _transaction(common) as (folder, data):
        item = data['entries'].get(job_id)
        if item is None or item['state'] != 'failed':
            raise SwarmError('Only failed queue entries can be retried')
        _check_runnable(root, common, job_id)
        if confirm:
            item['state'] = 'queued'
            item['last_result'] = None
            _event(data, 'retried', job_id)
            _write(folder, data)
    return {'id': job_id, 'state': 'queued' if confirm else 'dry-run',
            'notice': 'A retry reuses the existing worktree, including any previous edits.'}


def recover(target: Path, job_id: str, confirm: bool = False) -> dict:
    """Manual restoration of abandoned queue claims after confirming the owner is gone."""
    if not ID.fullmatch(job_id):
        raise SwarmError('Invalid job ID')
    _, common = _repo(target)
    with _transaction(common) as (folder, data):
        item = data['entries'].get(job_id)
        if item is None or item['state'] != 'claimed':
            raise SwarmError('Only claimed queue entries can be recovered')
        pid = item['claim']['pid']
        if _pid_alive(pid):
            raise SwarmError('Queue owner PID still alive; refusing recovery')
        if confirm:
            item['state'] = 'failed'
            item['claim'] = None
            item['last_result'] = {'state': 'failed', 'error': 'Operator recovered abandoned queue claim'}
            _event(data, 'recovered', job_id)
            _write(folder, data)
    return {'id': job_id, 'state': 'failed' if confirm else 'dry-run',
            'notice': 'Recovery does not stop Codex, clear scheduler reservations or restart jobs. Inspect the original worktree first.'}
