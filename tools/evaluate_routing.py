"""Offline routing benchmark: no models, APIs, credentials or telemetry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from forgequorum.routing import recommend  # noqa: E402


def evaluate(path: Path) -> dict:
    total = 0
    correct = 0
    mismatches = []
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        fixture = json.loads(line)
        decision = recommend(fixture['task'])
        actual = {'skill': decision['skill'], 'agent': decision['agents'][0] if decision['agents'] else None}
        expected = {'skill': fixture['skill'], 'agent': fixture['agent']}
        total += 1
        if actual == expected:
            correct += 1
        else:
            mismatches.append({'line': line_no, 'task': fixture['task'], 'expected': expected, 'actual': actual})
    if not total:
        raise ValueError('No benchmark fixtures')
    return {'total': total, 'correct': correct, 'accuracy': round(correct / total, 4),
            'mismatches': mismatches, 'scope': 'Offline deterministic rule coverage, not LLM quality.'}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', type=Path, default=ROOT/'evals/routing.jsonl')
    args = parser.parse_args()
    report = evaluate(args.fixtures)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report['mismatches'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
