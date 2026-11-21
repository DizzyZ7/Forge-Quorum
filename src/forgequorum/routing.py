"""Auditable, offline task recommendations. This is NOT an autonomous model runner."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .profiles import selections
from .registry import AGENTS, SKILLS


@dataclass(frozen=True)
class Rule:
    skill: str
    agents: tuple[str, ...]
    signals: tuple[str, ...]
    rationale: str


RULES = (
    Rule('security-gate', ('security-auditor', 'threat-modeler', 'reviewer'),
         ('security', 'vulnerab', 'auth', 'xss', 'csrf', 'injection', 'secret', 'audit',
          'безопас', 'уязвим', 'авторизац', 'пентест', 'инъекц'), 'Security boundaries and abuse cases'),
    Rule('incident-triage', ('debugger', 'devops-engineer', 'observability-engineer'),
         ('incident', 'outage', 'production down', 'downtime', 'crash', 'инцидент',
          'авария', 'недоступ', 'падает прод', 'сбой'), 'Operational incident response'),
    Rule('data-migration', ('database-engineer', 'python-backend', 'reviewer'),
         ('migration', 'migrate', 'schema', 'backfill', 'postgres', 'sql',
          'миграц', 'схем', 'таблиц', 'баз данн'), 'Database correctness and migrations'),
    Rule('performance-lab', ('performance-engineer', 'repo-explorer', 'test-engineer'),
         ('performance', 'latency', 'slow', 'throughput', 'optimiz', 'memory leak',
          'ускор', 'оптимиз', 'медлен', 'производительн', 'нагрузк'), 'Measured performance tuning'),
    Rule('automation-hardening', ('integration-engineer', 'python-backend', 'test-engineer'),
         ('telegram', 'redis', 'webhook', 'queue', 'retry', 'worker', 'bot', 'идемпотент',
          'очеред', 'бот', 'вебхук', 'воркер', 'повторн'), 'Reliable asynchronous automation'),
    Rule('ship-api', ('api-designer', 'python-backend', 'test-engineer'),
         ('fastapi', 'endpoint', 'rest', 'openapi', 'graphql', 'backend', 'api',
          'апи', 'эндпоинт', 'бэкенд', 'интеграц'), 'Stable API and integration contracts'),
    Rule('repair-bug', ('debugger', 'test-engineer', 'reviewer'),
         ('bug', 'fix', 'broken', 'regression', 'error', 'exception', 'ошибк', 'баг',
          'почин', 'исправ', 'сломал', 'не работает'), 'Root cause and regression protection'),
    Rule('release-ready', ('release-manager', 'devops-engineer', 'reviewer'),
         ('release', 'deploy', 'publish', 'rollback', 'ci/cd', 'релиз', 'деплой',
          'публикац', 'выкат', 'откат'), 'Release gates and rollback readiness'),
    Rule('deep-review', ('reviewer', 'security-auditor', 'test-engineer'),
         ('review', 'pull request', 'code review', 'ревью', 'провер', 'аудит кода'),
         'Independent review and verified findings'),
    Rule('repo-onboarding', ('repo-explorer', 'architect', 'docs-writer'),
         ('onboarding', 'understand repo', 'new repo', 'architecture map',
          'изучи репо', 'разберись в репо', 'структур проект'), 'Repository discovery and context'),
    Rule('build-feature', ('frontend-engineer', 'product-analyst', 'test-engineer'),
         ('frontend', 'react', 'vue', 'typescript', 'css', 'ui', 'ux', 'responsive',
          'интерфейс', 'верстк', 'дизайн', 'адаптив'), 'Client-side UI, UX and accessibility'),
    Rule('build-feature', ('planner', 'architect', 'test-engineer'),
         ('feature', 'implement', 'build', 'create', 'develop', 'add', 'фич',
          'разработ', 'созда', 'добав', 'реализ'), 'Feature delivery and verification'),
)


def recommend(task: str, profile: str = 'full', max_agents: int = 3) -> dict:
    """Return deterministic ranked suggestions; no LLM inference or network calls."""
    if not task.strip():
        raise ValueError('Task description cannot be empty')
    if not 1 <= max_agents <= 6:
        raise ValueError('max_agents must be between 1 and 6')
    available_agents, available_skills = selections(
        profile, tuple(a.name for a in AGENTS), tuple(s.name for s in SKILLS)
    )
    normalized = re.sub(r'\s+', ' ', task.casefold())
    ranked = []
    for index, rule in enumerate(RULES):
        if rule.skill not in available_skills:
            continue
        signals = sorted({s for s in rule.signals if s in normalized}, key=lambda s: (-len(s), s))
        if signals:
            ranked.append((-len(signals), index, rule, signals))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1]))
        _, _, rule, signals = ranked[0]
        skill, rationale = rule.skill, rule.rationale
        candidates = rule.agents
    else:
        skill, rationale = 'route-task', 'General task routing (no specific keyword match)'
        signals = []
        candidates = ('planner', 'repo-explorer', 'reviewer')
    team = [name for name in candidates if name in available_agents][:max_agents]
    if not team:
        team = [a.name for a in AGENTS if a.name in available_agents][:max_agents]
    prompt = f'${skill} {task.strip()}'
    return {
        'profile': profile,
        'skill': skill,
        'agents': team,
        'rationale': rationale,
        'matched_signals': signals,
        'prompt': prompt,
        'note': 'Offline keyword recommendation only; Codex decides which agents actually run.',
    }
