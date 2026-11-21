"""Minimal opt-in, local-only checkpoints. Never capture code, diffs or secrets."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .stack import detect_stack


def context_summary(root: Path) -> dict:
    stack = detect_stack(root)
    return {
        'target': str(root.resolve()),
        'recommended_profile': stack['recommended_profile'],
        'languages': [item['name'] for item in stack['languages']],
        'evidence': {item['name']: item['evidence'] for item in stack['languages'][:8]},
        'files_inspected': stack['files_inspected'],
        'scan_truncated': stack['scan_truncated'],
        'contains_agents_md': (root / 'AGENTS.md').is_file() and not (root / 'AGENTS.md').is_symlink(),
        'privacy': 'File names only: no source content, environment variables, transcript or git diff.',
    }


def create_checkpoint(root: Path, note: str = '') -> Path:
    """Only explicit invocation writes a note; no automatic session monitoring."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Target must be an existing non-symlink directory')
    folder = root / '.forgequorum' / 'checkpoints'
    if folder.is_symlink() or folder.parent.is_symlink():
        raise ValueError('Refusing checkpoint directory symlink')
    if len(note) > 4000:
        raise ValueError('Note is too long (max 4000 characters)')
    folder.mkdir(parents=True, exist_ok=True)
    # Keep checkpoint metadata local by default, without rewriting the user's
    # root .gitignore or recording any session transcript.
    exclusion = folder.parent / '.gitignore'
    if exclusion.is_symlink():
        raise ValueError('Refusing .forgequorum/.gitignore symlink')
    if not exclusion.exists():
        try:
            with exclusion.open('x', encoding='utf-8') as out:
                out.write('*\n!/.gitignore\n')
        except FileExistsError:
            pass
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10] + '.json'
    dest = folder / name
    data = {'format': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'note': note, 'context': context_summary(root)}
    # x means no overwrite; readable only by owner on POSIX where possible.
    import os
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write('\n')
    return dest
