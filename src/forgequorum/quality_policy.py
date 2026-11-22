"""Opt-in declarative test requirements. Never accepts shell commands."""
from __future__ import annotations

import json
from pathlib import Path

POLICY_FILE = 'forgequorum.quality.json'
MAX_SIZE = 16384
KNOWN_GATES = frozenset({
    'go-test', 'cargo-test', 'python-unittest', 'js-test', 'maven-test',
    'gradle-test', 'swift-test', 'dart-test', 'ruby-test',
})


def read_policy(root: Path) -> dict:
    file = root / POLICY_FILE
    if file.is_symlink():
        raise ValueError('Quality policy cannot be a symlink')
    if not file.exists():
        return {'schema': 1, 'required_gates': [], 'source': 'default'}
    if not file.is_file() or file.stat().st_size > MAX_SIZE:
        raise ValueError('Quality policy is not a regular JSON file within size limits')
    try:
        data = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('Quality policy is not valid UTF-8 JSON') from exc
    if (not isinstance(data, dict) or set(data) != {'schema', 'required_gates'}
            or type(data['schema']) is not int or data['schema'] != 1
            or not isinstance(data['required_gates'], list)
            or not 1 <= len(data['required_gates']) <= len(KNOWN_GATES)
            or any(not isinstance(name, str) or name not in KNOWN_GATES for name in data['required_gates'])
            or len(set(data['required_gates'])) != len(data['required_gates'])):
        raise ValueError('Quality policy must list unique known gate names')
    return {**data, 'source': POLICY_FILE}


def assess(policy: dict, planned: list[dict], results: list[dict] | None = None) -> dict:
    detected = {item['name'] for item in planned}
    required = policy['required_gates']
    missing = [name for name in required if name not in detected]
    reported = {item['name']: item['status'] for item in results or []}
    failed = [name for name in required if results is not None and reported.get(name) != 'passed']
    return {'required_gates': required, 'missing_gates': missing, 'failed_required_gates': failed,
            'source': policy['source'], 'ok': not missing and not failed}
