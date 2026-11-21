"""Polyglot installation profiles. A profile is a curated catalog, not an execution runtime."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    description: str
    agents: tuple[str, ...]
    skills: tuple[str, ...]


BASE = ('architect', 'planner', 'repo-explorer', 'reviewer', 'test-engineer', 'security-auditor')
WORKFLOWS = ('route-task', 'build-feature', 'repair-bug', 'deep-review', 'pr-preflight', 'test-strategy')


def pack(description: str, roles: tuple[str, ...], skills: tuple[str, ...]) -> Profile:
    # dict.fromkeys preserves display order while deduplicating common capabilities.
    return Profile(description, tuple(dict.fromkeys(BASE + roles)), tuple(dict.fromkeys(WORKFLOWS + skills)))


PROFILES: dict[str, Profile] = {
    'python': pack('Python apps, APIs and automation', ('python-backend','api-designer','database-engineer','integration-engineer','debugger'), ('ship-api','data-migration','automation-hardening')),
    'web': pack('Web and full-stack (TypeScript/JS, Python, PHP, Ruby, UI)', ('frontend-engineer','node-backend','python-backend','php-engineer','ruby-engineer','api-designer','database-engineer','accessibility-engineer','uiux-designer'), ('ship-api','polyglot-feature','accessibility-audit')),
    'backend': pack('Mixed-language APIs, distributed services and event processing', ('api-designer','node-backend','java-engineer','go-engineer','dotnet-engineer','python-backend','integration-engineer','database-engineer'), ('ship-api','polyglot-feature','data-migration','concurrency-review')),
    'node': pack('Node.js, TypeScript, NestJS and API services', ('node-backend','frontend-engineer','api-designer','database-engineer','qa-automation'), ('ship-api','polyglot-feature','test-strategy')),
    'java': pack('Java, Spring Boot and Gradle/Maven', ('java-engineer','api-designer','database-engineer','qa-automation'), ('ship-jvm-service','data-migration','concurrency-review')),
    'kotlin': pack('Kotlin, Ktor and JVM coroutines', ('kotlin-engineer','java-engineer','api-designer','database-engineer'), ('ship-jvm-service','concurrency-review','ship-api')),
    'go': pack('Go services and networking', ('go-engineer','api-designer','network-engineer','qa-automation'), ('ship-go-service','concurrency-review','ship-api')),
    'rust': pack('Rust systems, crates and services', ('rust-engineer','systems-engineer','cpp-engineer','performance-engineer'), ('ship-rust-crate','systems-safety','concurrency-review')),
    'dotnet': pack('.NET, C# and ASP.NET Core', ('dotnet-engineer','api-designer','database-engineer','desktop-engineer'), ('ship-dotnet','ship-api','cross-platform-release')),
    'php': pack('PHP, Laravel and Symfony', ('php-engineer','frontend-engineer','database-engineer','api-designer'), ('ship-api','polyglot-feature','data-migration')),
    'ruby': pack('Ruby, Rails and background jobs', ('ruby-engineer','frontend-engineer','database-engineer','integration-engineer'), ('ship-api','automation-hardening','data-migration')),
    'systems': pack('C/C++, OS integration, native code and concurrency', ('cpp-engineer','systems-engineer','rust-engineer','embedded-engineer','shell-engineer','performance-engineer'), ('systems-safety','concurrency-review','performance-lab')),
    'embedded': pack('MCU, RTOS, firmware and hardware integration', ('embedded-engineer','cpp-engineer','systems-engineer','qa-automation'), ('systems-safety','test-strategy','cross-platform-release')),
    'mobile': pack('Android, iOS, Swift and Flutter', ('android-engineer','swift-engineer','flutter-engineer','mobile-qa','accessibility-engineer','uiux-designer'), ('build-mobile','accessibility-audit','cross-platform-release')),
    'desktop': pack('Cross-platform and native desktop apps', ('desktop-engineer','dotnet-engineer','cpp-engineer','swift-engineer','systems-engineer','qa-automation'), ('build-desktop','cross-platform-release','systems-safety')),
    'games': pack('Unity, Unreal and Godot game development', ('game-engineer','cpp-engineer','dotnet-engineer','uiux-designer','qa-automation','performance-engineer'), ('gameplay-iteration','performance-lab','test-strategy')),
    'data': pack('SQL, ETL/ELT, Spark, Airflow, Kafka and dbt', ('data-engineer','database-engineer','python-backend','integration-engineer','privacy-engineer'), ('data-pipeline','data-migration','privacy-review')),
    'ml': pack('ML, RAG, inference and MLOps', ('ml-engineer','mlops-engineer','data-engineer','python-backend','privacy-engineer'), ('ml-lifecycle','data-pipeline','privacy-review')),
    'scientific': pack('Scientific and numerical computing: R, Julia and MATLAB', ('scientific-engineer','ml-engineer','data-engineer','performance-engineer'), ('test-strategy','performance-lab','architecture-decision')),
    'functional': pack('Scala, Elixir, Erlang, Haskell and F#', ('functional-engineer','java-engineer','dotnet-engineer','systems-engineer'), ('concurrency-review','architecture-decision','test-strategy')),
    'cloud': pack('Cloud, Kubernetes, IaC, SRE and platform engineering', ('cloud-architect','terraform-engineer','kubernetes-engineer','sre-engineer','devops-engineer','network-engineer','observability-engineer'), ('infrastructure-plan','kubernetes-operations','incident-triage','release-ready')),
    'security': pack('Security, threat modeling, privacy and supply chain', ('threat-modeler','dependency-auditor','privacy-engineer','network-engineer','qa-automation'), ('security-gate','privacy-review','systems-safety','test-strategy')),
    'infra': pack('DevOps, reliability, observability and incidents', ('devops-engineer','sre-engineer','kubernetes-engineer','terraform-engineer','observability-engineer','performance-engineer','release-manager'), ('incident-triage','infrastructure-plan','kubernetes-operations','performance-lab','release-ready')),
    'qa': pack('QA, automation, accessibility and cross-platform testing', ('qa-automation','mobile-qa','accessibility-engineer','debugger','performance-engineer'), ('test-strategy','accessibility-audit','deep-review')),
    'full': Profile('All available roles and skills; large catalog for mixed monorepos', (), ()),
}


def profile_names() -> tuple[str, ...]:
    return tuple(PROFILES)


def selections(profile: str, all_agents: tuple[str, ...], all_skills: tuple[str, ...]) -> tuple[set[str], set[str]]:
    if profile == 'full':
        return set(all_agents), set(all_skills)
    if profile not in PROFILES:
        raise ValueError(f'Unknown profile: {profile}')
    selection = PROFILES[profile]
    agents, skills = set(selection.agents), set(selection.skills)
    if not agents.issubset(all_agents) or not skills.issubset(all_skills):
        raise ValueError('Installation profile references missing agents or skills')
    return agents, skills
