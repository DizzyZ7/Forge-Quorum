"""Curated installation profiles; every profile includes its own routing skill."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    description: str
    agents: tuple[str, ...]
    skills: tuple[str, ...]


PROFILES: dict[str, Profile] = {
    'python': Profile(
        'Python services, APIs, databases and debugging (10 agents / 8 skills)',
        ('architect', 'planner', 'repo-explorer', 'python-backend', 'api-designer',
         'database-engineer', 'debugger', 'test-engineer', 'reviewer', 'security-auditor'),
        ('route-task', 'build-feature', 'repair-bug', 'deep-review', 'security-gate',
         'ship-api', 'data-migration', 'pr-preflight'),
    ),
    'web': Profile(
        'Full-stack product and frontend work (10 agents / 7 skills)',
        ('architect', 'planner', 'repo-explorer', 'product-analyst', 'frontend-engineer',
         'python-backend', 'api-designer', 'test-engineer', 'reviewer', 'docs-writer'),
        ('route-task', 'build-feature', 'repair-bug', 'deep-review', 'ship-api',
         'docs-sync', 'pr-preflight'),
    ),
    'security': Profile(
        'Security assessment and safe remediation (8 agents / 5 skills)',
        ('planner', 'repo-explorer', 'security-auditor', 'threat-modeler',
         'dependency-auditor', 'reviewer', 'test-engineer', 'python-backend'),
        ('route-task', 'repair-bug', 'deep-review', 'security-gate', 'pr-preflight'),
    ),
    'infra': Profile(
        'Operations, performance, incidents and reliability (9 agents / 7 skills)',
        ('architect', 'repo-explorer', 'devops-engineer', 'observability-engineer',
         'performance-engineer', 'database-engineer', 'debugger', 'reviewer',
         'release-manager'),
        ('route-task', 'incident-triage', 'performance-lab', 'release-ready',
         'automation-hardening', 'deep-review', 'pr-preflight'),
    ),
}


def profile_names() -> tuple[str, ...]:
    return ('python', 'web', 'security', 'infra', 'full')


def selections(profile: str, all_agents: tuple[str, ...], all_skills: tuple[str, ...]) -> tuple[set[str], set[str]]:
    if profile == 'full':
        return set(all_agents), set(all_skills)
    if profile not in PROFILES:
        raise ValueError(f'Unknown profile: {profile}')
    selection = PROFILES[profile]
    result = set(selection.agents), set(selection.skills)
    if not result[0].issubset(all_agents) or not result[1].issubset(all_skills):
        raise ValueError('Installation profile references missing agents or skills')
    return result
