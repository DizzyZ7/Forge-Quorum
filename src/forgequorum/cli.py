"""Safe, dependency-free project installer for native Codex agents and skills."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib

from .registry import AGENTS, AGENTS_BLOCK, CONFIG, SKILLS, VERSION, payload
from .profiles import PROFILES, profile_names
from .routing import recommend
from .stack import detect_stack
from .quality import run_verification
from .session import context_summary, create_checkpoint
from .swarm import (SwarmError, plan, create_job, inspect_job, list_jobs,
                    execute_job, cleanup_job, run_batch, review_job)
from .swarm_control import recovery, request_cancel, conflicts, verify_job, usage_report
from .handoff import handoff
from .scheduler import status as scheduler_status, configure as scheduler_configure, release as scheduler_release
from .queue import enqueue, snapshot as queue_snapshot, dispatch as queue_dispatch, reprioritize, requeue, recover as queue_recover, cancel_queued, observe
from .transfer import transfer as queue_transfer

MANIFEST = Path('.forgequorum/manifest.json')
START = '<!-- forge-quorum:start -->'
END = '<!-- forge-quorum:end -->'


class InstallError(Exception):
    pass


def digest(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def read_text(path: Path) -> str:
    # Preserve original line endings in existing project instructions.
    return path.read_bytes().decode('utf-8')


def assert_safe_path(root: Path, rel: Path) -> Path:
    if rel.is_absolute() or '..' in rel.parts or rel == Path('.'):
        raise InstallError(f'Unsafe managed path: {rel}')
    current = root
    if current.is_symlink():
        raise InstallError(f'Refusing symlink root: {root}')
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise InstallError(f'Refusing symlink in managed path: {current}')
    return current


def atomic_write(file: Path, content: str) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.forgequorum-', dir=file.parent, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
            out.write(content)
        os.replace(temp, file)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_manifest(root: Path) -> dict | None:
    path = assert_safe_path(root, MANIFEST)
    if not path.exists():
        return None
    try:
        data = json.loads(read_text(path))
    except (ValueError, OSError) as e:
        raise InstallError(f'Invalid manifest: {e}') from e
    if not isinstance(data, dict) or not isinstance(data.get('managed_files'), dict):
        raise InstallError('Invalid manifest schema; refusing to overwrite')
    if type(data.get('format')) is not int or data['format'] not in (1, 2):
        raise InstallError('Unsupported manifest version')
    if not isinstance(data.get('version'), str):
        raise InstallError('Missing manifest package version')
    if type(data.get('agents_md_preexisting')) is not bool:
        raise InstallError('Invalid AGENTS.md ownership marker')
    if data.get('agents_md_separator') not in ('', '\n', '\n\n'):
        raise InstallError('Invalid AGENTS.md separator')
    profile = data.get('profile', 'full')
    if not isinstance(profile, str) or profile not in profile_names():
        raise InstallError('Invalid installation profile in manifest')
    if data['format'] == 1 and 'profile' in data:
        raise InstallError('Unsupported profile in legacy manifest')
    allowed = set(payload()) | {'.codex/config.toml', '.forgequorum/config.example.toml'}
    normalized_files: dict[str, str] = {}
    for rel, sha in data['managed_files'].items():
        # v0.1 on Windows wrote config.toml with backslash separators.
        # Normalize those legacy paths before applying the strict allowlist.
        if not isinstance(rel, str):
            raise InstallError(f'Invalid managed path: {rel!r}')
        name = rel.replace('\\', '/')
        # This allowlist is essential: uninstall must NEVER trust arbitrary paths
        # from an editable JSON manifest, even if their digest matches.
        if name not in allowed or name in normalized_files:
            raise InstallError(f'Manifest contains an unrecognized or duplicate managed path: {rel!r}')
        if not isinstance(sha, str) or re.fullmatch(r'[0-9a-f]{64}', sha) is None:
            raise InstallError(f'Invalid digest for manifest entry: {rel!r}')
        assert_safe_path(root, Path(name))
        normalized_files[name] = sha
    data['managed_files'] = normalized_files
    return data


def plan_install(root: Path, profile: str | None = None) -> tuple[dict[Path, str], list[str], dict]:
    """Preflight every managed write; never overwrite unowned or edited files."""
    previous = load_manifest(root)
    old_profile = previous.get('profile', 'full') if previous else None
    # Resolve auto to a concrete profile before recording it in the manifest.
    selected_profile = (old_profile or detect_stack(root)['recommended_profile']) if profile == 'auto' else (profile or old_profile or 'full')
    if selected_profile not in profile_names():
        raise InstallError(f'Unknown profile: {selected_profile}')
    if old_profile is not None and selected_profile != old_profile:
        raise InstallError(f'Installed profile is {old_profile!r}; uninstall before changing to {selected_profile!r}')
    owned = previous['managed_files'] if previous else {}
    additions: dict[str, str] = payload(selected_profile)
    config = Path('.codex/config.toml')
    if (root / config).exists() and not (root / config).is_file():
        raise InstallError('Config path exists but is not a file')
    if (root / config).exists() and config.as_posix() not in owned:
        additions['.forgequorum/config.example.toml'] = CONFIG
    else:
        additions[config.as_posix()] = CONFIG
    modifications: dict[Path, str] = {}
    tracked: dict[str, str] = {}
    skipped: list[str] = []
    for name, content in additions.items():
        rel = Path(name)
        target = assert_safe_path(root, rel)
        if target.exists():
            if not target.is_file():
                raise InstallError(f'Not a regular file: {target}')
            current = read_text(target)
            if name in owned and digest(current) != owned[name]:
                raise InstallError(f'Previously managed file was edited: {name}; make a backup and resolve manually')
            if name not in owned:
                if current == content:
                    skipped.append(f'Existing identical file retained (unmanaged): {name}')
                    continue
                raise InstallError(f'File already exists (unmanaged): {name}; will not overwrite')
            if current != content:
                modifications[rel] = content
        else:
            modifications[rel] = content
        tracked[name] = digest(content)

    # Retain previously managed files even when new versions do not include them.
    # This makes upgrade behavior non-destructive; doctor can flag stale files.
    for name, sha in owned.items():
        if name not in tracked:
            tracked[name] = sha

    agents_rel = Path('AGENTS.md')
    agents_path = assert_safe_path(root, agents_rel)
    if agents_path.exists() and not agents_path.is_file():
        raise InstallError('AGENTS.md is not a regular file')
    was_preexisting = bool(previous.get('agents_md_preexisting')) if previous else agents_path.exists()
    existing = read_text(agents_path) if agents_path.exists() else ''
    separator = previous.get('agents_md_separator', '') if previous else ''
    if START in existing or END in existing:
        if previous is None:
            raise InstallError('An existing managed AGENTS.md block has no manifest; refusing to adopt it')
        if existing.count(START) != 1 or existing.count(END) != 1:
            raise InstallError('AGENTS.md contains invalid or duplicate managed markers')
        start = existing.index(START)
        end = existing.index(END) + len(END)
        if existing[start:end] != AGENTS_BLOCK:
            raise InstallError('AGENTS.md managed section was edited; refusing to overwrite')
    else:
        separator = ('\n' if existing and not existing.endswith('\n') else '') + ('\n' if existing else '')
        modifications[agents_rel] = existing + separator + AGENTS_BLOCK + '\n'

    new_manifest = {
        'format': 2,
        'version': VERSION,
        'profile': selected_profile,
        'agents_md_preexisting': was_preexisting,
        'agents_md_separator': separator,
        'managed_files': dict(sorted(tracked.items())),
    }
    manifest_content = json.dumps(new_manifest, ensure_ascii=False, indent=2) + '\n'
    if previous is None or read_text(root / MANIFEST) != manifest_content:
        modifications[MANIFEST] = manifest_content
    return modifications, skipped, new_manifest


def install(root: Path, dry_run: bool = False, profile: str | None = None) -> tuple[int, list[str]]:
    if not root.is_dir():
        raise InstallError(f'Target must be an existing directory: {root}')
    changes, skipped, _ = plan_install(root, profile)
    if dry_run:
        return len(changes), [f'WOULD WRITE {p.as_posix()}' for p in changes] + skipped
    # Every touched path has been preflighted. In an I/O failure we restore
    # prior content to avoid an incomplete installation.
    snapshots = {rel: read_text(root / rel) if (root / rel).exists() else None for rel in changes}
    written: list[Path] = []
    try:
        for rel, content in changes.items():
            atomic_write(root / rel, content)
            written.append(rel)
    except OSError as e:
        for rel in reversed(written):
            try:
                if snapshots[rel] is None:
                    (root / rel).unlink(missing_ok=True)
                else:
                    atomic_write(root / rel, snapshots[rel])
            except OSError:
                pass
        raise InstallError(f'Write failed (rollback attempted): {e}') from e
    return len(changes), [f'INSTALLED {p.as_posix()}' for p in changes] + skipped


def check(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    old = load_manifest(root)
    if not old:
        errors.append('Not installed: run forgequorum init --target <directory>')
        return errors, warnings
    for name, expected in old['managed_files'].items():
        path = assert_safe_path(root, Path(name))
        if not path.exists():
            errors.append(f'Missing: {name}')
            continue
        if digest(read_text(path)) != expected:
            errors.append(f'Modified: {name}')
        if name.endswith('.toml'):
            try:
                parsed = tomllib.loads(read_text(path))
                if '/agents/' in name and not all(isinstance(parsed.get(k), str) and parsed[k] for k in ('name', 'description', 'developer_instructions')):
                    errors.append(f'Invalid agent metadata: {name}')
            except tomllib.TOMLDecodeError as e:
                errors.append(f'Invalid TOML in {name}: {e}')
        if name.endswith('SKILL.md'):
            content = read_text(path)
            if not content.startswith('---\n') or '\nname: ' not in content or '\ndescription: ' not in content:
                errors.append(f'Invalid skill frontmatter: {name}')
    agents = assert_safe_path(root, Path('AGENTS.md'))
    if not agents.exists() or read_text(agents).count(AGENTS_BLOCK) != 1:
        errors.append('AGENTS.md managed block missing or modified')
    config = root / '.codex/config.toml'
    if config.exists():
        try:
            tomllib.loads(read_text(config))
        except tomllib.TOMLDecodeError as e:
            errors.append(f'Invalid project Codex config: {e}')
    else:
        warnings.append('No project .codex/config.toml; merge .forgequorum/config.example.toml if desired')
    if not shutil.which('codex'):
        warnings.append('Codex CLI was not found on PATH; generated assets can still be validated')
    return errors, warnings


def uninstall(root: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    old = load_manifest(root)
    if old is None:
        return 0, ['Nothing to uninstall']
    conflicts: list[str] = []
    removable: list[Path] = []
    for name, expected in old['managed_files'].items():
        rel = Path(name)
        path = assert_safe_path(root, rel)
        if path.exists() and digest(read_text(path)) != expected:
            conflicts.append(name)
        else:
            removable.append(rel)
    agents_rel = Path('AGENTS.md')
    agents_file = assert_safe_path(root, agents_rel)
    existing = read_text(agents_file) if agents_file.exists() else ''
    block_present = existing.count(AGENTS_BLOCK) == 1
    if not block_present:
        conflicts.append('AGENTS.md managed block')
    output = [f'WOULD REMOVE {p.as_posix()}' if dry_run else f'REMOVED {p.as_posix()}' for p in removable]
    if conflicts:
        output.extend(f'KEEP (modified): {x}' for x in conflicts)
    if dry_run:
        if block_present:
            output.append('WOULD REMOVE managed AGENTS.md block')
        return len(removable), output
    for rel in removable:
        (root / rel).unlink(missing_ok=True)
        parent = (root / rel).parent
        while parent != root and parent != (root / '.forgequorum'):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    if block_present:
        # The injected block is always surrounded by the same exact suffix.
        prefix, suffix = existing.split(AGENTS_BLOCK, 1)
        separator = old.get('agents_md_separator', '')
        if separator and prefix.endswith(separator):
            prefix = prefix[:-len(separator)]
        if suffix.startswith('\n'):
            suffix = suffix[1:]
        remaining = prefix + suffix
        if not remaining and not old.get('agents_md_preexisting', False):
            agents_file.unlink(missing_ok=True)
        else:
            atomic_write(agents_file, remaining)
        output.append('REMOVED managed AGENTS.md block')
    remaining_files = {n: old['managed_files'][n] for n in conflicts if n in old['managed_files']}
    if remaining_files or not block_present:
        old['managed_files'] = remaining_files
        atomic_write(root / MANIFEST, json.dumps(old, ensure_ascii=False, indent=2) + '\n')
    else:
        (root / MANIFEST).unlink(missing_ok=True)
        try:
            (root / '.forgequorum').rmdir()
        except OSError:
            pass
    return len(removable), output


def status(root: Path) -> dict:
    """Machine-readable installed state (no secret file contents)."""
    old = load_manifest(root)
    errors, warnings = check(root)
    if old is None:
        return {'installed': False, 'ok': False, 'version': None, 'profile': None,
                'managed_files': 0, 'agents': 0, 'skills': 0,
                'errors': errors, 'warnings': warnings}
    entries = tuple(old['managed_files'])
    return {
        'installed': True, 'ok': not errors,
        'version': old['version'], 'profile': old.get('profile', 'full'),
        'managed_files': len(entries),
        'agents': sum(p.startswith('.codex/agents/') for p in entries),
        'skills': sum(p.startswith('.agents/skills/') for p in entries),
        'errors': errors, 'warnings': warnings,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='forgequorum', description='ForgeQuorum: native Codex agent/skill pack')
    p.add_argument('--version', action='version', version=VERSION)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('init', 'doctor', 'status', 'uninstall'):
        cmd = sub.add_parser(command)
        cmd.add_argument('--target', type=Path, default=Path('.'), help='Existing project folder (default: current directory)')
        if command in ('init', 'uninstall'):
            cmd.add_argument('--dry-run', action='store_true')
        if command == 'init':
            cmd.add_argument('--profile', choices=profile_names() + ('auto',), default=None,
                             help='Choose a language/role profile or auto-detect from filenames')
        if command in ('doctor', 'status'):
            cmd.add_argument('--json', action='store_true', help='Machine-readable result')
    sub.add_parser('list', help='List bundled agents and workflow skills')
    sub.add_parser('profiles', help='List curated agent/skill profiles')
    inspect = sub.add_parser('inspect', help='Offline filename-based project stack inspection')
    inspect.add_argument('--target', type=Path, default=Path('.'))
    inspect.add_argument('--json', action='store_true')
    rec = sub.add_parser('recommend', help='Recommend a workflow and agent team offline')
    rec.add_argument('task', help='Describe the engineering task (English or Russian)')
    rec.add_argument('--profile', choices=profile_names() + ('auto',), default='full')
    rec.add_argument('--target', type=Path, default=None, help='Optional project directory to detect stack from filenames')
    rec.add_argument('--max-agents', type=int, default=3)
    rec.add_argument('--json', action='store_true')
    verify = sub.add_parser('verify', help='Plan polyglot quality gates; --run is required to execute project code')
    verify.add_argument('--target', type=Path, default=Path('.'))
    verify.add_argument('--run', action='store_true', help='Opt in to running selected project tests; may have side effects')
    verify.add_argument('--timeout', type=int, default=120, help='Per-gate timeout, 1..1800 seconds')
    verify.add_argument('--json', action='store_true')
    context = sub.add_parser('context', help='Show a compact filename-only context report')
    context.add_argument('--target', type=Path, default=Path('.'))
    context.add_argument('--json', action='store_true')
    checkpoint = sub.add_parser('checkpoint', help='Explicitly write a local-only, no-code session checkpoint')
    checkpoint.add_argument('--target', type=Path, default=Path('.'))
    checkpoint.add_argument('--note', default='', help='Optional user-authored, non-sensitive note (max 4000 chars)')
    hook = sub.add_parser('hook-context', help='Opt-in Codex SessionStart hook (read-only; accepts JSON stdin)')
    scheduler = sub.add_parser('scheduler', help='Cross-process Codex admission and reserved-token budgets')
    scheduler_sub = scheduler.add_subparsers(dest='scheduler_command', required=True)
    scheduler_sub.add_parser('status', help='Show global slots and conservative token ledger')
    sc = scheduler_sub.add_parser('configure', help='Change global policy only when no jobs run')
    sc.add_argument('--max-running', type=int, default=2)
    sc.add_argument('--daily-tokens', type=int, default=0)
    sc.add_argument('--confirm', action='store_true')
    sr = scheduler_sub.add_parser('release', help='Manually release abandoned slot after PID inspection')
    sr.add_argument('ticket', help='32-character scheduler ticket')
    sr.add_argument('--confirm', action='store_true')
    queue = sub.add_parser('queue', help='Priority and dependency-aware repository job queue')
    queue_sub = queue.add_subparsers(dest='queue_command', required=True)
    for name in ('add', 'status', 'watch', 'run', 'priority', 'retry', 'recover', 'cancel', 'transfer'):
        q = queue_sub.add_parser(name)
        q.add_argument('--target', type=Path, default=Path('.'), help='Git repository root or subdirectory')
        if name == 'add':
            q.add_argument('task', help='Task to perform in its own worktree')
            q.add_argument('--priority', type=int, default=0, help='-100..100, highest first')
            q.add_argument('--after', nargs='*', default=[], metavar='JOB_ID',
                           help='Existing queued jobs that must complete before this job starts')
            q.add_argument('--profile', choices=profile_names() + ('auto',), default='auto')
            q.add_argument('--max-agents', type=int, default=3)
            q.add_argument('--gate', choices=('order', 'verified', 'transferred'), default='order',
                           help='Dependency policy: order-only (legacy), verified or explicitly transferred')
        if name == 'transfer':
            q.add_argument('job_id', help='Destination queued job ID')
            q.add_argument('--from', dest='source_job', required=True, help='Completed and freshly verified dependency job ID')
            q.add_argument('--apply', action='store_true', help='Explicitly stage a verified source patch in destination worktree')
        if name in ('priority', 'retry', 'recover', 'cancel'):
            q.add_argument('job_id', help='12-character job ID')
            q.add_argument('--confirm', action='store_true')
        if name == 'priority':
            q.add_argument('priority', type=int, help='New priority -100..100')
        if name == 'watch':
            q.add_argument('--seconds', type=float, default=20, help='Bounded foreground watch duration 0..300s')
            q.add_argument('--interval', type=float, default=1, help='Poll interval 0.1..30s')
        if name == 'run':
            q.add_argument('--execute', action='store_true', help='Explicitly authorize model execution')
            q.add_argument('--max-jobs', type=int, default=1, help='Number of jobs to attempt (1..12)')
            q.add_argument('--parallel', type=int, default=1, help='Concurrent local workers (1..4)')
            q.add_argument('--timeout', type=int, default=900)
            q.add_argument('--reserve-tokens', type=int, default=0)
            q.add_argument('--wait-seconds', type=int, default=0)
    swarm = sub.add_parser('swarm', help='Plan and execute opt-in Codex jobs in isolated Git worktrees')
    swarm_sub = swarm.add_subparsers(dest='swarm_command', required=True)
    for name in ('plan', 'start', 'run', 'status', 'list', 'cleanup', 'batch', 'review', 'cancel', 'recover', 'conflicts', 'verify', 'usage', 'handoff'):
        cmd = swarm_sub.add_parser(name)
        cmd.add_argument('--target', type=Path, default=Path('.'))
        cmd.add_argument('--json', action='store_true')
        if name in ('plan', 'start'):
            cmd.add_argument('task', help='Non-sensitive task description')
            cmd.add_argument('--profile', choices=profile_names() + ('auto',), default='auto')
            cmd.add_argument('--max-agents', type=int, default=3)
        if name in ('run', 'status', 'cleanup', 'review', 'cancel', 'recover', 'verify'):
            cmd.add_argument('job_id', help='12-character ForgeQuorum job ID')
        if name == 'run':
            cmd.add_argument('--execute', action='store_true', help='Explicitly run Codex in this worktree')
            cmd.add_argument('--timeout', type=int, default=900)
        if name in ('cancel', 'recover'):
            cmd.add_argument('--confirm', action='store_true', help='Confirm non-destructive state transition')
        if name == 'verify':
            cmd.add_argument('--run', action='store_true', help='Execute selected project tests in the job worktree')
            cmd.add_argument('--timeout', type=int, default=120)
        if name in ('conflicts', 'handoff'):
            cmd.add_argument('job_ids', nargs='+', help='Between 2 and 12 worktree job IDs')
        if name == 'usage':
            cmd.add_argument('job_ids', nargs='*', help='Selected jobs or omit for all jobs')
        if name == 'cleanup':
            cmd.add_argument('--confirm', action='store_true', help='Remove only a clean worktree; preserve its branch')
        if name in ('run', 'batch'):
            cmd.add_argument('--reserve-tokens', type=int, default=0,
                             help='Per-job token reservation used by the scheduler; not a hard spending cap')
            cmd.add_argument('--wait-seconds', type=int, default=120 if name == 'batch' else 0,
                             help='Wait 0..300s for a global slot')
        if name == 'batch':
            cmd.add_argument('job_ids', nargs='+', help='Up to 12 distinct prepared job IDs')
            cmd.add_argument('--execute', action='store_true', help='Authorize Codex execution for each supplied job')
            cmd.add_argument('--max-parallel', type=int, default=2, help='Bound concurrent jobs in this batch to 1..4')
            cmd.add_argument('--timeout', type=int, default=900, help='Seconds per job, 30..3600')
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == 'scheduler':
        try:
            if args.scheduler_command == 'status':
                result = scheduler_status()
            elif args.scheduler_command == 'configure':
                result = scheduler_configure(args.max_running, args.daily_tokens, args.confirm)
            else:
                result = scheduler_release(args.ticket, args.confirm)
        except (SwarmError, OSError, ValueError) as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == 'queue':
        try:
            root = args.target.absolute()
            if args.queue_command == 'add':
                result = enqueue(root, args.task, args.priority, args.after, args.profile, args.max_agents, args.gate)
            elif args.queue_command == 'transfer':
                result = queue_transfer(root, args.job_id, args.source_job, args.apply)
            elif args.queue_command == 'status':
                result = queue_snapshot(root)
            elif args.queue_command == 'watch':
                for item in observe(root, args.seconds, args.interval):
                    print(json.dumps(item, ensure_ascii=False), flush=True)
                return 0
            elif args.queue_command == 'run':
                result = queue_dispatch(root, args.max_jobs, args.parallel, args.timeout,
                                        args.reserve_tokens, args.wait_seconds, args.execute)
            elif args.queue_command == 'priority':
                result = reprioritize(root, args.job_id, args.priority, args.confirm)
            elif args.queue_command == 'retry':
                result = requeue(root, args.job_id, args.confirm)
            elif args.queue_command == 'cancel':
                result = cancel_queued(root, args.job_id, args.confirm)
            else:
                result = queue_recover(root, args.job_id, args.confirm)
        except (SwarmError, OSError, ValueError) as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print('Queue watch interrupted', file=sys.stderr)
            return 130
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.queue_command == 'run' and args.execute and result['state'] == 'partial-failure':
            return 1
        return 0
    if args.command == 'swarm':
        try:
            root = args.target.absolute()
            if args.swarm_command == 'plan':
                result = plan(root, args.task, args.profile, args.max_agents)
            elif args.swarm_command == 'start':
                result = create_job(root, args.task, args.profile, args.max_agents)
            elif args.swarm_command == 'run':
                result = execute_job(root, args.job_id, args.timeout, args.execute, args.reserve_tokens, args.wait_seconds)
            elif args.swarm_command == 'status':
                result = inspect_job(root, args.job_id)
            elif args.swarm_command == 'list':
                result = list_jobs(root)
            elif args.swarm_command == 'batch':
                result = run_batch(root, args.job_ids, args.timeout, args.max_parallel, args.execute, args.reserve_tokens, args.wait_seconds)
            elif args.swarm_command == 'review':
                result = review_job(root, args.job_id)
            elif args.swarm_command == 'conflicts':
                result = conflicts(root, args.job_ids)
            elif args.swarm_command == 'handoff':
                result = handoff(root, args.job_ids)
            elif args.swarm_command == 'usage':
                result = usage_report(root, args.job_ids)
            elif args.swarm_command == 'cancel':
                result = request_cancel(root, args.job_id, args.confirm)
            elif args.swarm_command == 'recover':
                result = recovery(root, args.job_id, args.confirm)
            elif args.swarm_command == 'verify':
                result = verify_job(root, args.job_id, args.run, args.timeout)
            else:
                result = cleanup_job(root, args.job_id, args.confirm)
        except (SwarmError, OSError, ValueError) as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if ((args.swarm_command in ('run', 'batch') and args.execute and result.get('state') != 'completed')
                     or (args.swarm_command == 'verify' and args.run and result.get('state') != 'passed')) else 0
    if args.command == 'list':
        print(f'{len(AGENTS)} specialized agents:')
        for agent in AGENTS:
            print(f'  {agent.name:23} {agent.description}')
        print(f'\n{len(SKILLS)} workflow skills:')
        for skill in SKILLS:
            print(f'  {skill.name:23} {skill.description}')
        return 0
    if args.command == 'profiles':
        for name in profile_names():
            if name == 'full':
                print(f'  full       All {len(AGENTS)} agents and {len(SKILLS)} skills')
            else:
                print(f'  {name:10} {PROFILES[name].description}')
        print('  auto       Detect the repository stack from filenames; no project code is executed')
        return 0
    if args.command == 'inspect':
        try:
            report = detect_stack(args.target.absolute())
        except ValueError as e:
            print(f'ERROR: {e}', file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"Recommended profile: {report['recommended_profile']}")
            print(f"Inspected: {report['files_inspected']} files (truncated: {report['scan_truncated']})")
            for lang in report['languages']:
                print(f"  {lang['name']:14} score={lang['score']:4} evidence={', '.join(lang['evidence'])}")
            print(report['note'])
        return 0
    if args.command == 'recommend':
        try:
            stack = detect_stack(args.target.absolute()) if args.target is not None else None
            if args.profile == 'auto' and stack is None:
                raise ValueError('--profile auto requires --target')
            effective_profile = stack['recommended_profile'] if args.profile == 'auto' else args.profile
            decision = recommend(args.task, effective_profile, args.max_agents, stack)
            if stack is not None:
                decision['stack'] = stack
        except ValueError as e:
            print(f'ERROR: {e}', file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(decision, ensure_ascii=False, indent=2))
        else:
            print(f"Suggested skill: ${decision['skill']}")
            print(f"Suggested team: {', '.join(decision['agents'])}")
            print(f"Why: {decision['rationale']}")
            print(f"Prompt: {decision['prompt']}")
            print(decision['note'])
        return 0
    if args.command == 'hook-context':
        # Never read transcripts, prompts, environment variables or code.
        # Input is a small JSON event supplied by Codex, not arbitrary Python.
        try:
            raw = sys.stdin.read(65537)
            if len(raw) > 65536:
                raise ValueError('Hook input too large')
            data = json.loads(raw) if raw.strip() else {}
            if not isinstance(data, dict):
                raise ValueError('Expected JSON object')
            root = Path(data.get('cwd', '.')).absolute()
            ctx = context_summary(root)
            short = f"ForgeQuorum: profile={ctx['recommended_profile']}; languages={','.join(ctx['languages'][:5])}; files={ctx['files_inspected']}. Verify repository guidance before edits."
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': short}}))
            return 0
        except (ValueError, OSError, TypeError) as e:
            print(f'ForgeQuorum context hook skipped: {e}', file=sys.stderr)
            return 0  # Advisory hooks must not break the parent session.
    if args.command in ('verify', 'context', 'checkpoint'):
        try:
            root = args.target.absolute()
            if args.command == 'verify':
                result = run_verification(root, timeout=args.timeout, run=args.run)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    for gate in result['gates']:
                        print(f"PLAN: {gate['name']}: {' '.join(gate['argv'])} ({gate['reason']})")
                    for gate in result.get('results', []):
                        print(f"RESULT: {gate['name']}: {gate['status']}")
                    print(result['notice'])
                return 0 if not args.run or result['ok'] else 1
            if args.command == 'context':
                result = context_summary(root)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"Profile: {result['recommended_profile']} | files: {result['files_inspected']}")
                    print('Languages: ' + ', '.join(result['languages']))
                    print(result['privacy'])
                return 0
            print('Saved local checkpoint: ' + str(create_checkpoint(root, args.note)))
            return 0
        except (ValueError, OSError) as e:
            print(f'ERROR: {e}', file=sys.stderr)
            return 1
    root: Path = args.target.absolute()
    try:
        if args.command == 'init':
            count, lines = install(root, args.dry_run, args.profile)
            for line in lines:
                print(line)
            print(f'\n{count} file(s) {"would change" if args.dry_run else "changed"}.')
            if not args.dry_run:
                print('Run: forgequorum doctor --target ' + str(root))
            return 0
        if args.command in ('doctor', 'status'):
            result = status(root)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.command == 'status':
                print(f"Installed: {result['installed']}, profile: {result['profile']}, version: {result['version']}")
                print(f"Assets: {result['agents']} agents, {result['skills']} skills")
                for msg in result['errors']:
                    print('ERROR: ' + msg)
                for msg in result['warnings']:
                    print('WARN: ' + msg)
            else:
                for msg in result['errors']:
                    print('ERROR: ' + msg)
                for msg in result['warnings']:
                    print('WARN: ' + msg)
                print(f"Result: {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")
            return 0 if result['ok'] else 1
        if args.command == 'uninstall':
            count, lines = uninstall(root, args.dry_run)
            for line in lines:
                print(line)
            print(f'{count} managed file(s) {"would be removed" if args.dry_run else "removed"}.')
            return 2 if any('KEEP (modified)' in x for x in lines) else 0
    except (InstallError, OSError, UnicodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 2
