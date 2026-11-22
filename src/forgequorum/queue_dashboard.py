"""Offline, read-only status board with explicitly requested static HTML export."""
from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
import tempfile

from .queue import dashboard
from .swarm import SwarmError


def render(info: dict) -> str:
    """No JavaScript, external resources, transcripts or network calls."""
    rows = []
    for item in info['items']:
        cells = [item['id'], item['state'], item['readiness'], str(item['priority']),
                 item['gate'], ', '.join(item['after']) or '—']
        rows.append('<tr>' + ''.join(f'<td>{escape(cell)}</td>' for cell in cells) + '</tr>')
    states = ', '.join(f'{escape(k)}: {v}' for k, v in sorted(info['states'].items())) or 'none'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>ForgeQuorum — Queue Dashboard</title><style>'
            ':root{color-scheme:light dark;font:16px system-ui}body{max-width:1100px;margin:4rem auto;padding:0 1.5rem}'
            'header{display:flex;justify-content:space-between;gap:1rem;align-items:center}'
            'table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:.8rem;border-bottom:1px solid #8885}'
            'th{background:#8882}tbody tr:hover{background:#8881}p{line-height:1.5;color:gray}'
            'code{font-family:ui-monospace,monospace} .frame{overflow-x:auto}</style></head><body>'
            '<header><h1>ForgeQuorum</h1><strong>Queue dashboard</strong></header>'
            f'<p>Jobs: {info["total"]} · Ready: {info["ready"]} · {states}</p>'
            '<p>Static snapshot of local metadata. No external requests, automatic refresh, or model execution.</p>'
            '<div class="frame"><table><thead><tr>'
            + ''.join(f'<th>{label}</th>' for label in ('Job', 'State', 'Readiness', 'Priority', 'Gate', 'Dependencies'))
            + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></body></html>')


def export(target: Path, output: Path) -> dict:
    """No overwrites or symlinks: publishing an HTML file is always opt-in."""
    info = dashboard(target)
    if not output.parent.is_dir() or output.parent.is_symlink() or output.is_symlink() or output.exists():
        raise SwarmError('Dashboard output must be a new file in an existing directory (no symlinks)')
    parent = output.parent
    fd, temporary = tempfile.mkstemp(prefix='.fq-dashboard-', suffix='.tmp', dir=parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as writer:
            writer.write(render(info))
        # os.link refuses accidental overwrite between preflight and write.
        os.link(temporary, output)
    except (OSError, ValueError) as exc:
        raise SwarmError(f'Cannot create dashboard file safely: {type(exc).__name__}') from exc
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'file': str(output.absolute()), 'total': info['total'], 'ready': info['ready'],
            'notice': 'Static HTML snapshot generated locally; no server or network calls.'}
