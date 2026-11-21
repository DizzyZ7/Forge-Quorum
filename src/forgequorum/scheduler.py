"""Local, cross-process admission control for explicitly authorized Codex jobs.

Reservations bound *admission*, not real-time usage or billing. No daemon, no
background tasks, no global network services and no automatic stale-lock removal.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from time import monotonic, sleep
from uuid import uuid4

from .swarm import SwarmError

SCHEMA = 1
MAX_PARALLEL = 8
MAX_TOKENS = 10**12


def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _base_dir() -> Path:
    custom = os.environ.get('FORGEQUORUM_STATE_DIR')
    base = Path(custom) if custom is not None else Path.home() / '.forgequorum' / 'scheduler'
    if not base.is_absolute():
        raise SwarmError('FORGEQUORUM_STATE_DIR must be an absolute path')
    # Prevent following a symlink in the managed path (not a full defense
    # against another user with write access to the same home directory).
    for part in (base, *list(base.parents)[:-1]):
        if part.is_symlink():
            raise SwarmError('Refusing a symlink in scheduler storage path')
    return base


def _directory() -> Path:
    base = _base_dir()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if base.is_symlink():
        raise SwarmError('Refusing symlinked scheduler storage')
    return base


def _initial() -> dict:
    return {'schema': SCHEMA, 'max_running': 2, 'daily_token_limit': 0,
            'active': {}, 'daily_usage': {}}


def _validate(data: dict) -> dict:
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA
            or type(data.get('max_running')) is not int
            or not 1 <= data['max_running'] <= MAX_PARALLEL
            or type(data.get('daily_token_limit')) is not int
            or not 0 <= data['daily_token_limit'] <= MAX_TOKENS
            or not isinstance(data.get('active'), dict)
            or not isinstance(data.get('daily_usage'), dict)):
        raise SwarmError('Invalid scheduler state; refusing execution')
    for entry in data['active'].values():
        if (not isinstance(entry, dict) or type(entry.get('pid')) is not int
                or not isinstance(entry.get('job_id'), str)
                or not isinstance(entry.get('repository'), str)
                or not isinstance(entry.get('date'), str)
                or type(entry.get('reserved_tokens')) is not int
                or not 0 <= entry['reserved_tokens'] <= MAX_TOKENS):
            raise SwarmError('Corrupt active reservation')
    for day, used in data['daily_usage'].items():
        if not isinstance(day, str) or type(used) is not int or not 0 <= used <= MAX_TOKENS * 100:
            raise SwarmError('Corrupt scheduler token ledger')
    return data


def _read(base: Path) -> dict:
    path = base / 'state.json'
    if path.is_symlink():
        raise SwarmError('Refusing symlinked scheduler state')
    if not path.exists():
        return _initial()
    try:
        return _validate(json.loads(path.read_text(encoding='utf-8')))
    except (ValueError, OSError, UnicodeError) as exc:
        raise SwarmError('Cannot read scheduler state safely') from exc


def _write(base: Path, data: dict) -> None:
    target = base / 'state.json'
    if target.is_symlink():
        raise SwarmError('Refusing symlinked scheduler state')
    fd, temp = tempfile.mkstemp(prefix='.fq-scheduler-', dir=base)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            os.chmod(temp, 0o600)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def _transaction():
    base = _directory()
    lock = base / '.mutex'
    if lock.is_symlink():
        raise SwarmError('Refusing symlinked scheduler lock')
    # Atomic directory creation implements a mutex on local filesystems.
    # If the owner crashes, fail closed. Never remove a lock owned by another process.
    deadline = monotonic() + 3
    while True:
        try:
            lock.mkdir(mode=0o700)
            break
        except FileExistsError as exc:
            if monotonic() >= deadline:
                raise SwarmError('Scheduler lock is busy or abandoned; inspect .mutex before recovery') from exc
            sleep(0.025)
    try:
        data = _read(base)
        yield base, data
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def status() -> dict:
    with _transaction() as (_, data):
        return {
            'max_running': data['max_running'],
            'daily_token_limit': data['daily_token_limit'],
            'today_utc': _today(),
            'charged_tokens_today': data['daily_usage'].get(_today(), 0),
            'active_count': len(data['active']),
            'active': [{'ticket': ticket, 'job_id': rec['job_id'], 'pid': rec['pid'],
                        'reserved_tokens': rec['reserved_tokens'], 'since': rec.get('since')}
                       for ticket, rec in sorted(data['active'].items())],
            'note': 'Admissions and conservative token reservations, not a hard monetary cap; no daemon or automatic reaping.',
        }


def configure(max_running: int, daily_token_limit: int, confirm: bool = False) -> dict:
    if type(max_running) is not int or not 1 <= max_running <= MAX_PARALLEL:
        raise SwarmError(f'max_running must be 1..{MAX_PARALLEL}')
    if type(daily_token_limit) is not int or not 0 <= daily_token_limit <= MAX_TOKENS:
        raise SwarmError('daily_token_limit must be 0..10^12')
    if not confirm:
        return {'state': 'dry-run', 'max_running': max_running,
                'daily_token_limit': daily_token_limit,
                'note': 'Pass --confirm to save policy; 0 disables token admission quota.'}
    with _transaction() as (base, data):
        if data['active']:
            raise SwarmError('Cannot change scheduling policy while jobs hold slots')
        if daily_token_limit and data['daily_usage'].get(_today(), 0) > daily_token_limit:
            raise SwarmError('New daily cap is below tokens already charged today')
        data['max_running'] = max_running
        data['daily_token_limit'] = daily_token_limit
        _write(base, data)
    return {'state': 'configured', 'max_running': max_running,
            'daily_token_limit': daily_token_limit}


def claim(repository: str, job_id: str, reserve_tokens: int = 0, wait_seconds: int = 0) -> str:
    """Reserve one process slot and conservative token quota across CLI invocations.

    A crash intentionally leaves the slot and reservation charged; manual release
    is required after verifying that no process is still running.
    """
    if type(reserve_tokens) is not int or not 0 <= reserve_tokens <= MAX_TOKENS:
        raise SwarmError('reserve_tokens must be 0..10^12')
    if type(wait_seconds) is not int or not 0 <= wait_seconds <= 300:
        raise SwarmError('wait_seconds must be 0..300')
    deadline = monotonic() + wait_seconds
    while True:
        slot_full = False
        with _transaction() as (base, data):
            if any(v['job_id'] == job_id and v['repository'] == repository
                   for v in data['active'].values()):
                raise SwarmError('This job already holds a global scheduler slot')
            limit = data['daily_token_limit']
            if limit and not reserve_tokens:
                raise SwarmError('A positive --reserve-tokens value is required when daily token quota is enabled')
            day = _today()
            if limit and data['daily_usage'].get(day, 0) + reserve_tokens > limit:
                raise SwarmError('Daily token admission budget exhausted; no Codex execution launched')
            if len(data['active']) >= data['max_running']:
                slot_full = True
            else:
                ticket = uuid4().hex
                data['active'][ticket] = {'pid': os.getpid(), 'job_id': job_id,
                                          'repository': repository, 'date': day,
                                          'since': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                          'reserved_tokens': reserve_tokens}
                data['daily_usage'][day] = data['daily_usage'].get(day, 0) + reserve_tokens
                # Keep a bounded ledger of past days, never remove entries for
                # reservations still active across midnight.
                relevant = {x['date'] for x in data['active'].values()}
                dates = sorted(data['daily_usage'])[-40:]
                data['daily_usage'] = {key: value for key, value in data['daily_usage'].items()
                                       if key in relevant or key in dates}
                _write(base, data)
                return ticket
        if not slot_full or monotonic() >= deadline:
            raise SwarmError('Global concurrent Codex process limit reached; retry or use --wait-seconds')
        sleep(min(0.15, max(0, deadline - monotonic())))


def settle(ticket: str, reported_tokens: int | None = None) -> dict:
    """Release a claim. Unreported usage consumes full reservation conservatively."""
    if (reported_tokens is not None and
            (type(reported_tokens) is not int or reported_tokens < 0 or reported_tokens > MAX_TOKENS)):
        raise SwarmError('Invalid reported usage amount')
    with _transaction() as (base, data):
        record = data['active'].get(ticket)
        if record is None:
            raise SwarmError('Scheduler ticket not found; inspect before recovery')
        if record['pid'] != os.getpid():
            raise SwarmError('Cannot settle a slot owned by another process')
        charged = record['reserved_tokens'] if reported_tokens is None else reported_tokens
        day = record['date']
        data['daily_usage'][day] = max(0, data['daily_usage'].get(day, 0)
                                        + charged - record['reserved_tokens'])
        del data['active'][ticket]
        _write(base, data)
    return {'ticket': ticket, 'tokens_charged': charged,
            'source': 'reported' if reported_tokens is not None else 'reservation'}


def _pid_alive(pid: int) -> bool:
    """Check ownership without ever sending an OS signal to the process."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        open_process = kernel.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit = kernel.GetExitCodeProcess
        get_exit.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit.restype = wintypes.BOOL
        close_handle = kernel.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: no such PID
                return False
            raise SwarmError('Cannot query process ownership safely')
        try:
            exit_code = wintypes.DWORD()
            if not get_exit(handle, ctypes.byref(exit_code)):
                raise SwarmError('Cannot query owner process state')
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            close_handle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise SwarmError('Cannot verify the owner PID') from exc
    return True


def release(ticket: str, confirm: bool = False) -> dict:
    """Manual orphan recovery. Does not kill or touch processes or worktrees."""
    if not isinstance(ticket, str) or len(ticket) != 32 or any(c not in '0123456789abcdef' for c in ticket):
        raise SwarmError('Invalid ticket')
    with _transaction() as (base, data):
        record = data['active'].get(ticket)
        if record is None:
            raise SwarmError('Unknown scheduler ticket')
        if not confirm:
            return {'state': 'dry-run', 'ticket': ticket, 'job_id': record['job_id'],
                    'note': 'Check that the original Codex process and children are stopped before --confirm.'}
        pid = record['pid']
        if _pid_alive(pid):
            raise SwarmError('Owner PID is still present; refusing manual release')
        # Keep the entire reservation charged; true token usage is unknown.
        del data['active'][ticket]
        _write(base, data)
    return {'state': 'released', 'ticket': ticket, 'tokens_charged': record['reserved_tokens'],
            'note': 'Original reserved tokens remain charged. No Codex process was terminated.'}
