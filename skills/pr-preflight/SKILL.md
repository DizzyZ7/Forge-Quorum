---
name: pr-preflight
description: Prepare a small, evidence-backed pull request with safe review boundaries.
---

# pr-preflight

## Trigger
Before opening a PR or submitting a patch for review.

## Procedure
1. Check git status and identify unrelated user changes without discarding them.
2. Summarize diff and verify acceptance criteria are addressed.
3. Run relevant formatter, lint, typing and tests or explain omissions.
4. Audit accidental credentials, binary artifacts and dependency changes.
5. Check compatibility and rollout considerations.
6. Draft an informative title/body with reproduction and testing details.
7. Never push, merge or force-update without explicit approval.

## Delegation policy
Use reviewer as independent check; route security-sensitive changes to security-auditor.

## Done when
PR summary, actual checks and outstanding risks with no invented CI results.
