---
name: route-task
description: Choose the smallest sufficient set of Codex subagents for a task; avoid unnecessary fan-out.
---

# route-task

## Trigger
When a request spans domains, is ambiguous, or could be delegated independently.

## Procedure
1. Classify the request: discovery, coding, verification, release or incident.
2. For a trivial/local change: solve directly; do not spawn agents.
3. For cross-cutting tasks: first ask repo-explorer for evidence and planner for a dependency map when they add value.
4. Delegate only truly independent jobs, normally 2-4; give distinct file ownership or read-only scopes.
5. Set expected output, shared acceptance criteria, time/budget constraints and stop conditions for each subagent.
6. Wait for reports; reconcile contradictions in the parent, which remains accountable.
7. Run final tests and review; do not present agent opinions as verified facts.

## Delegation policy
Use native Codex subagents only when available; if not, follow the same stages serially. Never claim agents ran if they did not.

## Done when
A single consolidated result with evidence, change summary and limitations.
