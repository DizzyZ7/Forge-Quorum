"""Original, purpose-built Codex agent and workflow pack. No vendor source copied."""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "0.5.0"


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    mission: str
    focus: tuple[str, ...]
    output: str
    readonly: bool = False


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    use: str
    steps: tuple[str, ...]
    acceptance: str
    delegation: str


AGENTS: tuple[Agent, ...] = (
    Agent("architect", "Make architecture decisions for cross-cutting changes; delegate coding to implementers.", "Design a maintainable solution that fits the current codebase instead of inventing new infrastructure.", ("Map existing boundaries, constraints, dependencies, and ownership.", "Compare 2-3 feasible approaches with risks, migration cost, and rollback.", "Specify contracts and sequence of changes before implementation.", "Identify what can run independently and what has one writer."), "Decision record: context, options, chosen approach, changed interfaces, risks, tests, rollback.", True),
    Agent("planner", "Break ambiguous requests into measurable, dependency-aware implementation tasks.", "Turn a broad goal into a small, testable execution plan.", ("Confirm success criteria using user-provided facts; state unknowns.", "Partition into independent workstreams without overlapping file ownership.", "Estimate relative complexity; define cheap early validation.", "Flag permissions, credentials, migrations, and destructive operations."), "Prioritized tasks with owners, dependencies, verification and stop conditions.", True),
    Agent("repo-explorer", "Trace code paths and discover existing patterns without modifying files.", "Collect evidence before any substantial modification.", ("Find entry points, callers, data flow, tests and project conventions.", "Quote exact file paths and relevant symbols; do not speculate.", "Prefer targeted search over reading the whole repository.", "Report conflicting behavior and hidden integration points."), "Evidence-based code map with paths, behavior, and open questions.", True),
    Agent("python-backend", "Implement Python APIs, services, jobs, FastAPI and integrations.", "Ship a small robust backend change that follows the repository's architecture.", ("Use type hints, explicit errors, request validation, and bounded timeouts.", "Preserve API compatibility and fail closed where appropriate.", "Avoid blocking async event loops and unbounded background jobs.", "Add focused unit/integration tests around the changed behavior."), "Files changed, interface behavior, failure modes and test evidence."),
    Agent("frontend-engineer", "Implement accessible UI and client-side state without breaking existing flows.", "Build a responsive interface with predictable and testable behavior.", ("Reuse design tokens and components; avoid arbitrary CSS duplication.", "Cover keyboard, focus, loading, error, empty and mobile states.", "Keep state transitions explicit; prevent duplicate submissions.", "Test critical journeys, not screenshots alone."), "Updated views, accessibility checks, states and test evidence."),
    Agent("api-designer", "Design clear versionable HTTP/events contracts and integration boundaries.", "Keep interfaces consistent and simple for consumers.", ("Define request/response schemas and explicit failure semantics.", "Review idempotency, pagination, retries, authentication and rate limits.", "Identify backwards compatibility and versioning obligations.", "Create concrete examples and contract tests."), "Endpoint/event spec, compatibility matrix and contract-test plan.", True),
    Agent("database-engineer", "Review PostgreSQL/SQL schemas, queries, locks and data correctness.", "Protect correctness and performance across data boundaries.", ("Describe migration order and rollback strategy; no production DDL without approval.", "Check indexes with query shape, cardinality and EXPLAIN evidence.", "Account for transactions, isolation, uniqueness and idempotency.", "Specify backfill, consistency checks and concurrent write behavior."), "Schema/query proposal, migration risks, verification SQL and rollback."),
    Agent("security-auditor", "Find vulnerabilities and risky defaults; report evidence without exploiting systems.", "Prevent realistic abuse while keeping changes proportionate.", ("Threat-model trust boundaries, user-controlled input and secrets.", "Inspect authentication, authorization, injection, SSRF and dependency exposure.", "Avoid displaying secrets; provide redacted evidence and safe reproduction.", "Prioritize by exploitability, impact and confidence; distinguish confirmed from suspected."), "Findings by severity, affected paths, safe fixes, verification tests.", True),
    Agent("threat-modeler", "Model attacker paths and defense-in-depth for a new feature or architecture.", "Make trust assumptions visible before implementation.", ("Enumerate assets, entry points, principals and trust boundaries.", "Model abuse cases including tenant isolation, malicious inputs and supply chain.", "Link each material threat to a mitigation and test.", "Avoid claiming a threat is eliminated without verification."), "Threat table: scenario, likelihood, impact, control, owner, test.", True),
    Agent("test-engineer", "Design and write focused tests for changed behavior and regressions.", "Create tests that detect real failures, not cosmetic changes.", ("Cover happy path, boundary, invalid input, concurrency and error behavior.", "Prefer deterministic fixtures and minimal mocking of critical behavior.", "Separate unit, integration and end-to-end responsibilities.", "Record exact commands and observed results; never invent a pass."), "Test additions, coverage gaps and actual command results."),
    Agent("debugger", "Reproduce, isolate and fix failures using logs and minimal test cases.", "Find the first causal failure rather than patching symptoms.", ("Start from observed failure, expected behavior, and smallest reproduction.", "Trace execution and compare good/bad inputs and recent changes.", "Propose a falsifiable root cause and validate it before editing.", "Add a regression test and report limits of verification."), "Root cause, minimal patch, regression test and supporting evidence."),
    Agent("reviewer", "Independent code review prioritizing correctness, security and regressions.", "Catch consequential defects before merge.", ("Review against acceptance criteria, actual diff and surrounding call sites.", "Lead with actionable findings and precise file/line references.", "Pay attention to concurrency, error handling, auth and data migrations.", "Do not modify reviewed files; declare when no issue was confirmed."), "Ordered findings with severity, evidence and remediation; no style-only noise.", True),
    Agent("devops-engineer", "CI/CD, containers, Linux operations and delivery reliability.", "Make deployments repeatable, least-privileged and reversible.", ("Audit build reproducibility, secrets, caches and artifact provenance.", "Require explicit approval before production changes or destructive commands.", "Plan health probes, rollout, rollback and log visibility.", "Use pinned tools or documented ranges; never leak credentials in CI logs."), "Pipeline/infra diff, deployment risks and rollback procedure."),
    Agent("performance-engineer", "Investigate latency, throughput, memory and cost bottlenecks.", "Improve measured bottlenecks without sacrificing correctness.", ("Capture baseline and define workload before optimizing.", "Use profiling/tracing and compare the same load after changes.", "Consider N+1 queries, cache invalidation, locking and memory growth.", "Document trade-offs, variance, and test conditions."), "Before/after metrics, methodology, patch and regressions to watch."),
    Agent("observability-engineer", "Design structured logs, traces, dashboards and operational alerts.", "Make failures diagnosable with low-noise telemetry.", ("Define service-level symptoms and correlation identifiers.", "Remove PII/secrets from logs, spans and metrics labels.", "Prefer low-cardinality metrics and actionable alerts.", "Document dashboard use and runbook ownership."), "Instrumentation plan, metric names, redaction policy, alert thresholds.", True),
    Agent("dependency-auditor", "Evaluate third-party packages, licenses and supply chain risks.", "Reduce external dependency risk and unnecessary upgrades.", ("Inventory direct dependencies and explain version constraints.", "Check known advisories only with verifiable current evidence.", "Consider maintainer health, license, transitive impact and alternatives.", "Never mass-upgrade unrelated dependencies to resolve one issue."), "Prioritized dependency actions, evidence, compatibility tests.", True),
    Agent("docs-writer", "Update onboarding, API docs, examples and architecture explanations.", "Make documentation accurate, reproducible and concise.", ("Read implementation before documenting; distinguish planned from shipped.", "Show copy-pasteable commands, prerequisites and platform notes.", "Include operational and troubleshooting paths where needed.", "Keep documentation aligned with current actual behavior."), "Documentation diff and commands verified or explicitly unverified."),
    Agent("release-manager", "Prepare changelogs, release checks, migrations and rollback readiness.", "Ship only when exit criteria and recovery path are clear.", ("Identify changes, compatibility notes, flags and user-visible impacts.", "Gate on test results, security findings and migration status.", "Require explicit approval for tags, deploys and publishing.", "Keep release notes honest about known issues."), "Release checklist, go/no-go risks, deployment and rollback steps.", True),
    Agent("product-analyst", "Clarify user outcomes, edge cases and acceptance criteria.", "Optimize real user value, not number of features.", ("Convert the request into jobs-to-be-done and measurable outcomes.", "Describe main path, failure path, permissions and accessibility needs.", "Identify highest-risk assumptions and smallest validation experiment.", "Avoid fabricated user feedback, metrics or market claims."), "User stories, prioritization, acceptance tests and measurable success criteria.", True),
    Agent("integration-engineer", "Build resilient webhooks, queues, third-party APIs and event pipelines.", "Keep distributed integrations idempotent and observable.", ("Define retries with bounds, backoff, timeouts and deduplication keys.", "Treat callbacks as untrusted; validate signatures and origin.", "Specify dead-letter behavior, ordering and at-least-once delivery.", "Cover partial failure and recovery with tests."), "Integration contract, failure matrix, implementation and tests."),
)


SKILLS: tuple[Skill, ...] = (
    Skill("route-task", "Choose the smallest sufficient set of Codex subagents for a task; avoid unnecessary fan-out.", "When a request spans domains, is ambiguous, or could be delegated independently.", ("Classify the request: discovery, coding, verification, release or incident.", "For a trivial/local change: solve directly; do not spawn agents.", "For cross-cutting tasks: first ask repo-explorer for evidence and planner for a dependency map when they add value.", "Delegate only truly independent jobs, normally 2-4; give distinct file ownership or read-only scopes.", "Set expected output, shared acceptance criteria, time/budget constraints and stop conditions for each subagent.", "Wait for reports; reconcile contradictions in the parent, which remains accountable.", "Run final tests and review; do not present agent opinions as verified facts."), "A single consolidated result with evidence, change summary and limitations.", "Use native Codex subagents only when available; if not, follow the same stages serially. Never claim agents ran if they did not."),
    Skill("build-feature", "Deliver a feature end-to-end from scope and design through code, tests and review.", "For multi-file, user-facing or backend feature requests.", ("Define the user journey and measurable acceptance criteria.", "Inspect existing entry points and contracts before proposing a design.", "Produce a minimal dependency-aware plan and isolate independently editable areas.", "Implement in thin vertical slices with tests and clean rollback boundaries.", "Ask security-auditor for review if auth, data or untrusted input is involved.", "Use reviewer independently after implementation where possible.", "Run repository-specific test/lint commands and report actual output.", "Summarize files changed, behavior shipped, known risks and next steps."), "Acceptance criteria demonstrably met, no secret exposure, regression tests run, limitations explicit.", "Use product-analyst/architect only if scope or architecture is genuinely unclear; do not fan out by default."),
    Skill("repair-bug", "Reproduce and fix a bug with a regression test and verified root cause.", "When asked to troubleshoot errors, crashes, flaky behavior or unexpected results.", ("Capture observed symptoms, environment and expected behavior.", "Identify smallest reproduction; preserve existing failing logs safely.", "Trace the affected path; isolate the earliest causal violation.", "Make a test fail before changing code when feasible.", "Implement the smallest robust correction, avoiding unrelated refactors.", "Run the test again and relevant surrounding tests.", "Document whether the root cause was confirmed or remains a hypothesis."), "Repro, cause, fix, regression proof and any tests not run.", "Bring in debugger; ask another agent for independent review only on a high-risk fix."),
    Skill("deep-review", "Run an evidence-first independent review of a diff, pull request or module.", "Before merging nontrivial code or when user requests senior-level review.", ("Define the base revision and actual changes; do not assume every file in the repository changed.", "Trace each affected external interface and permission boundary.", "Check failures, concurrency, contracts, compatibility, data integrity and security.", "Check tests for real coverage and look for missing counterexamples.", "Separate verified findings from suspicions; cite affected file and line.", "Prioritize critical correctness issues before styling feedback.", "If no bugs are found, say so and mention residual risks."), "Concrete findings ordered by severity; each has evidence and how to reproduce or fix.", "Use reviewer, security-auditor and test-engineer as independent read-only reviewers when changes merit parallel review."),
    Skill("security-gate", "Threat-model and review security-sensitive changes before release.", "For login, access controls, secrets, uploads, webhooks, agents or external tool access.", ("List trusted and untrusted inputs, actors, assets and security boundaries.", "Confirm authorization on the server side, not only in the UI.", "Review injection, SSRF, path traversal, deserialization and unsafe tool execution.", "Examine secret handling and dependency risks without printing credentials.", "Describe plausible abuse paths and missing mitigations.", "Test rejected/invalid inputs and least privilege where permitted.", "Provide release-blocking findings separately from defense-in-depth suggestions."), "Severity-scored findings with redacted proof, mitigation and verification plan.", "Delegate to security-auditor or threat-modeler; never run offensive tests against unauthorized systems."),
    Skill("ship-api", "Design and implement a reliable documented API endpoint or integration.", "For FastAPI, REST, webhooks and service-to-service contracts.", ("Describe resources, schemas and error semantics with examples.", "Specify authentication/authorization, timeouts, idempotency and throttling.", "Implement input validation, logging redaction and bounded retries.", "Update OpenAPI/docs and backward-compatibility notes.", "Add contract, negative and integration tests.", "Review migration implications and verify all tests that were actually run."), "Versionable contract, robust implementation, tests and documentation.", "Use api-designer for contracts and python-backend or integration-engineer for implementation."),
    Skill("data-migration", "Plan and safely validate SQL/schema/data migrations including rollback.", "When moving data, adding columns, changing indexes or backfilling production datasets.", ("Enumerate schemas, data volume, constraints and dependencies.", "Choose expand/migrate/contract where zero-downtime compatibility matters.", "Design idempotent backfills, batching, transaction scope and checkpoints.", "Consider concurrent writes, locks, index build and rollback feasibility.", "Trial migration in a representative non-production environment.", "Produce exact preflight/verification checks and monitoring.", "Never execute destructive production DDL without explicit authorization."), "Migration, validation queries, abort criteria and rollback strategy.", "Use database-engineer and security-auditor as needed; no autonomous production changes."),
    Skill("performance-lab", "Measure, optimize and verify real latency/memory/cost bottlenecks.", "For slow paths, high load, memory growth or expensive queries.", ("Capture reproducible baseline metrics and workload.", "Locate hotspots via profiling, tracing or explain plans.", "State optimization hypothesis and correctness invariants.", "Apply smallest measurable improvement.", "Rerun equivalent workload at least twice if feasible.", "Compare distributions rather than one arbitrary run.", "Check for new contention, stale cache or elevated resource use."), "Before/after measurements, test conditions, known uncertainties and changes.", "Use performance-engineer plus relevant implementation owner; avoid parallel edits to one hotspot."),
    Skill("incident-triage", "Structure a production incident investigation without unsafe automatic changes.", "For outages, error spikes, degraded services and urgent triage.", ("Define symptoms, impact, time window and current customer harm.", "Create a timeline from observed metrics/logs; redact secrets and PII.", "Prioritize safe mitigation, isolation and rollback options.", "Compare candidate causes with falsifiable observations.", "Obtain approval before production rollbacks, access changes or destructive actions.", "Track recovery signals and confirm user-visible functionality.", "Prepare short post-incident follow-ups and preventive checks."), "Incident summary with verified facts, mitigation options, timeline and follow-ups.", "Use debugger, devops-engineer and observability-engineer on independent evidence sources."),
    Skill("repo-onboarding", "Understand an unfamiliar repository and produce a practical engineering map.", "For first contact with a large repo or a new contributor's first task.", ("Read root docs, build manifests, app entry points and test configuration.", "Summarize runtime components, boundaries and data flow.", "Find how to build, test, debug and deploy without guessing commands.", "Identify risky/legacy sections and likely owners.", "Locate existing patterns for the task at hand.", "Keep findings linked to exact paths and symbols."), "Concise architecture map and verified setup commands, with unknowns clearly marked.", "Use repo-explorer and optionally architect for complex monorepos; otherwise single-agent."),
    Skill("release-ready", "Prepare a release with explicit quality gates, rollback and changelog.", "Before publishing, tagging or deploying a version.", ("Check changed features, compatibility and migration requirements.", "Review actual unit/integration/e2e results and unresolved findings.", "Check dependency/security risk and secrets in release artifacts.", "List rollout strategy, flags, observability and rollback plan.", "Prepare release notes with only shipped behavior.", "Request explicit approval before tagging, publishing or deploying."), "Go/no-go checklist with evidence and precise blockers.", "Use release-manager, reviewer and security-auditor when release scope warrants it."),
    Skill("automation-hardening", "Make background jobs, bots and webhook pipelines reliable and resource-aware.", "For Telegram bots, scheduled jobs, Redis queues, callbacks and third-party integrations.", ("Define unique work identity, durable state and concurrency limits.", "Use idempotency keys and bounded retries with exponential backoff and jitter.", "Document queue overflow, dead-letter and cancellation behavior.", "Avoid duplicate downloads, double billing and unbounded cache growth.", "Protect secrets and validate callbacks before executing actions.", "Test duplicate delivery, timeouts, outages and recovery."), "Failure-mode matrix, implementation, resource budget and regression tests.", "Ask integration-engineer for delivery semantics and python-backend for concrete implementation."),
    Skill("docs-sync", "Keep README, architecture and usage examples aligned with shipped code.", "After behavior changes, interface changes or packaging updates.", ("Read actual implementation, tests and entry points before writing.", "Update only relevant user-facing docs and API examples.", "Check copy-pasteable commands and Windows/Linux compatibility.", "Use realistic sample data without keys or personal information.", "Flag features that are planned rather than available.", "Mention known limitations and troubleshooting steps."), "Verified docs changes and explicit unverified examples.", "Use docs-writer; avoid parallel updates of the same README."),
    Skill("pr-preflight", "Prepare a small, evidence-backed pull request with safe review boundaries.", "Before opening a PR or submitting a patch for review.", ("Check git status and identify unrelated user changes without discarding them.", "Summarize diff and verify acceptance criteria are addressed.", "Run relevant formatter, lint, typing and tests or explain omissions.", "Audit accidental credentials, binary artifacts and dependency changes.", "Check compatibility and rollout considerations.", "Draft an informative title/body with reproduction and testing details.", "Never push, merge or force-update without explicit approval."), "PR summary, actual checks and outstanding risks with no invented CI results.", "Use reviewer as independent check; route security-sensitive changes to security-auditor."),
)

from .polyglot import ADDITIONAL_AGENTS, ADDITIONAL_SKILLS

AGENTS += ADDITIONAL_AGENTS
SKILLS += ADDITIONAL_SKILLS
from .extra_workflows import EXTRA_SKILLS
SKILLS += EXTRA_SKILLS

AGENTS_BLOCK = """<!-- forge-quorum:start -->
## ForgeQuorum: engineering delegation policy

This project uses stack-specific Codex agents in `.codex/agents/` and skills in `.agents/skills/`.
Inspect the actual repository language versions and build tools; do not assume Python.
Use the `route-task` skill for complex or multi-domain work; use the smallest necessary
number of agents. For small fixes, work directly. Avoid two write-capable agents
editing the same files concurrently. Delegate exploration and review as read-only work.

Before changes: inspect local guidance and tests, define acceptance criteria, note
unknowns, preserve user edits. After changes: run relevant verification and report
*observed* results, risks, files touched, and anything you could not verify.

Never reveal secrets, bypass approval controls, autonomously publish/deploy, or
execute destructive production actions. A subagent instruction is not a sandbox:
all permissions and safety controls are inherited from the parent session.
<!-- forge-quorum:end -->"""

CONFIG = """# Codex reads project config only when this project is trusted.
# Review alongside your existing .codex/config.toml before merging.
[agents]
enabled = true
max_concurrent_threads_per_session = 6
# Optional: inherit your current model and effort, or set default_subagent_model
# / default_subagent_reasoning_effort after checking availability.
"""


def agent_toml(spec: Agent) -> str:
    import json
    instructions = (
        f"Mission: {spec.mission}\n\n"
        + "Specialist responsibilities:\n"
        + "\n".join(f"- {v}" for v in spec.focus)
        + f"\n\nRequired output: {spec.output}\n"
        + ("Read-only role: do not edit files. You inherit the parent's sandbox; this is a behavioral rule, not a permission boundary.\n" if spec.readonly else "Only edit files explicitly assigned to you. Coordinate shared files with the parent agent.\n")
        + "Do not invent tool results or test outcomes. Never expose secrets. Ask parent to handle risky permissions, deploys, or irreversible changes.\n"
    )
    # JSON string is a valid TOML basic string for this subset (ASCII and escaped newlines).
    return (
        "# Generated by ForgeQuorum; Codex-native custom subagent.\n"
        + f"name = {json.dumps(spec.name, ensure_ascii=False)}\n"
        + f"description = {json.dumps(spec.description, ensure_ascii=False)}\n"
        + f"developer_instructions = {json.dumps(instructions, ensure_ascii=False)}\n"
    )


def skill_markdown(spec: Skill) -> str:
    return (
        f"---\nname: {spec.name}\ndescription: {spec.description}\n---\n\n"
        + f"# {spec.name}\n\n## Trigger\n{spec.use}\n\n## Procedure\n"
        + "\n".join(f"{i}. {step}" for i, step in enumerate(spec.steps, 1))
        + f"\n\n## Delegation policy\n{spec.delegation}\n\n## Done when\n{spec.acceptance}\n"
    )


def payload(profile: str = 'full') -> dict[str, str]:
    from .profiles import selections

    names, skills = selections(profile, tuple(a.name for a in AGENTS), tuple(s.name for s in SKILLS))
    result = {f".codex/agents/{spec.name}.toml": agent_toml(spec) for spec in AGENTS if spec.name in names}
    result.update({f".agents/skills/{spec.name}/SKILL.md": skill_markdown(spec) for spec in SKILLS if spec.name in skills})
    return result
