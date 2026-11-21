---
name: release-ready
description: Prepare a release with explicit quality gates, rollback and changelog.
---

# release-ready

## Trigger
Before publishing, tagging or deploying a version.

## Procedure
1. Check changed features, compatibility and migration requirements.
2. Review actual unit/integration/e2e results and unresolved findings.
3. Check dependency/security risk and secrets in release artifacts.
4. List rollout strategy, flags, observability and rollback plan.
5. Prepare release notes with only shipped behavior.
6. Request explicit approval before tagging, publishing or deploying.

## Delegation policy
Use release-manager, reviewer and security-auditor when release scope warrants it.

## Done when
Go/no-go checklist with evidence and precise blockers.
