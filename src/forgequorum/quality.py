"""Explicit, deterministic verification plans for polyglot repositories.

No project command is executed unless the caller sets run=True. The plan is a
heuristic, not a sandbox or a complete test inventory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from .stack import detect_stack
from .quality_policy import read_policy, assess


def _regular(root: Path, relative: str) -> bool:
    """Only trust project files, never symlinks (including ancestor directories)."""
    path = root
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            return False
    return path.is_file()


def _script(root: Path, script: str) -> bool:
    """Read only package metadata, not arbitrary source files."""
    if not _regular(root, 'package.json'):
        return False
    file = root / 'package.json'
    if file.stat().st_size > 256 * 1024:
        return False
    try:
        data = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return False
    return isinstance(data, dict) and isinstance(data.get('scripts'), dict) and isinstance(data['scripts'].get(script), str) and bool(data['scripts'][script].strip())


def _node_manager(root: Path) -> str:
    # Respect lockfiles, not PATH precedence. Don't silently switch managers.
    if _regular(root, 'pnpm-lock.yaml'):
        return 'pnpm'
    if _regular(root, 'yarn.lock'):
        return 'yarn'
    if _regular(root, 'bun.lock') or _regular(root, 'bun.lockb'):
        return 'bun'
    return 'npm'


def _gate(name: str, argv: list[str], reason: str) -> dict[str, Any]:
    return {'name': name, 'argv': argv, 'reason': reason}


def verification_plan(root: Path, max_files: int = 5000) -> dict[str, Any]:
    """Build a conservative, executable-argument-only plan without side effects."""
    stack = detect_stack(root, max_files=max_files)
    selected: list[dict[str, Any]] = []
    add = selected.append
    if _regular(root, 'go.mod'):
        add(_gate('go-test', ['go', 'test', './...'], 'Go module detected'))
    if _regular(root, 'Cargo.toml'):
        add(_gate('cargo-test', ['cargo', 'test', '--all-targets'], 'Cargo manifest detected'))
    if _regular(root, 'pyproject.toml') or _regular(root, 'pytest.ini') or _regular(root, 'requirements.txt'):
        if (root / 'tests').is_dir() and not (root / 'tests').is_symlink():
            add(_gate('python-unittest', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                      'Python project with tests/; replace with pytest if appropriate'))
    if _script(root, 'test'):
        manager = _node_manager(root)
        add(_gate('js-test', [manager, 'run', 'test'], f'package.json scripts.test; lockfile selects {manager}'))
    if _regular(root, 'pom.xml'):
        add(_gate('maven-test', ['mvn', 'test'], 'Maven project detected'))
    if _regular(root, 'gradlew'):
        add(_gate('gradle-test', ['./gradlew', 'test'], 'Gradle wrapper detected'))
    elif _regular(root, 'gradlew.bat'):
        add(_gate('gradle-test', ['gradlew.bat', 'test'], 'Windows Gradle wrapper detected'))
    if _regular(root, 'Package.swift'):
        add(_gate('swift-test', ['swift', 'test'], 'Swift package detected'))
    if _regular(root, 'pubspec.yaml'):
        add(_gate('dart-test', ['dart', 'test'], 'Dart project detected; Flutter projects may need flutter test'))
    if _regular(root, 'Gemfile'):
        add(_gate('ruby-test', ['bundle', 'exec', 'rake', 'test'], 'Ruby project detected; confirm Rake test task exists'))
    # Do not guess a test runner for arbitrary PHP/C++, frontend apps, or
    # multi-repo layouts without a real project manifest or script.
    policy = read_policy(root)
    policy_status = assess(policy, selected)
    return {
        'target': str(root.resolve()),
        'quality_policy': policy_status,
        'profile': stack['recommended_profile'],
        'languages': [item['name'] for item in stack['languages']],
        'gates': selected,
        'planned': len(selected),
        'executed': False,
        'notice': ('Planning is read-only. --run executes project-defined test code, which may have '
                   'side effects or network access. Review gates before running; this is not a sandbox.'),
    }


def run_verification(root: Path, *, timeout: int = 120, run: bool = False) -> dict[str, Any]:
    if not 1 <= timeout <= 1800:
        raise ValueError('--timeout must be between 1 and 1800 seconds')
    plan = verification_plan(root)
    if not run:
        return plan
    plan['executed'] = True
    results = []
    for gate in plan['gates']:
        argv = gate['argv']
        exe = argv[0]
        if '/' not in exe and '\\' not in exe and not Path(exe).is_absolute() and shutil.which(exe) is None:
            results.append({'name': gate['name'], 'status': 'missing-tool', 'exit_code': None})
            continue
        try:
            # No shell, no automatic install, and no elevation. Deliberately
            # don't return raw output (it may contain credentials or PII).
            proc = subprocess.run(argv, cwd=root, capture_output=True, timeout=timeout, check=False)
            results.append({'name': gate['name'], 'status': 'passed' if proc.returncode == 0 else 'failed',
                            'exit_code': proc.returncode})
        except subprocess.TimeoutExpired:
            results.append({'name': gate['name'], 'status': 'timeout', 'exit_code': None})
        except OSError:
            results.append({'name': gate['name'], 'status': 'launch-error', 'exit_code': None})
    plan['results'] = results
    plan['quality_policy'] = assess(read_policy(root), plan['gates'], results)
    plan['ok'] = bool(results) and all(item['status'] == 'passed' for item in results) and plan['quality_policy']['ok']
    return plan
