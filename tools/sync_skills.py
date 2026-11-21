"""Reproducibly export Codex/ChatGPT plugin skills from the Python catalog.

Usage: python tools/sync_skills.py [--check]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from forgequorum.registry import SKILLS, skill_markdown  # noqa: E402

UI_NAMES = {
    'route-task': ('Route Engineering Task', 'Choose a small, accountable multi-agent team.'),
    'verification-loop': ('Verify Changes', 'Run evidence-backed quality gates before delivery.'),
    'context-checkpoint': ('Session Checkpoint', 'Make a concise, privacy-aware project handoff.'),
    'test-driven-loop': ('Test Driven Loop', 'Develop changes through failing then passing tests.'),
}


def build() -> dict[Path, str]:
    result = {}
    for skill in SKILLS:
        directory = REPO / 'skills' / skill.name
        result[directory / 'SKILL.md'] = skill_markdown(skill)
        if skill.name in UI_NAMES:
            label, description = UI_NAMES[skill.name]
            result[directory / 'agents' / 'openai.yaml'] = (
                'interface:\n'
                f'  display_name: "{label}"\n'
                f'  short_description: "{description}"\n'
                f'  default_prompt: "Use ${skill.name} to complete this task with verified results."\n'
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Fail if committed plugin skill files are stale')
    args = parser.parse_args()
    expected = build()
    existing = {p for p in (REPO / 'skills').rglob('*') if p.is_file()} if (REPO / 'skills').exists() else set()
    if args.check:
        wrong = [p for p, text in expected.items() if not p.is_file() or p.read_text(encoding='utf-8') != text]
        extra = existing - expected.keys()
        if wrong or extra:
            for p in wrong:
                print(f'Stale/missing: {p.relative_to(REPO)}')
            for p in sorted(extra):
                print(f'Unexpected file: {p.relative_to(REPO)}')
            return 1
        print(f'Skill exports synchronized: {len(SKILLS)} skills')
        return 0
    for path in existing - expected.keys():
        path.unlink()  # Only files under generated `skills/` directory.
    for path, text in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
    print(f'Exported {len(SKILLS)} portable skills')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
