---
name: verification-loop
description: Audit a change through build, test, behavior and security quality gates.
---

# verification-loop

## Trigger
Use after meaningful code changes, before releases or when a user requests proof of correctness.

## Procedure
1. Discover the repository build scripts and test framework; never assume a test runner exists.
2. Run fq verify for a read-only proposed gate list; use --run only with trusted project commands.
3. Run applicable lint/typecheck/build/integration/E2E as separate explicit actions.
4. Inspect failures for causality and rerun affected tests after a bounded fix.
5. Report exact commands and outcomes: passed, failed, skipped and not run.
6. For uncertain tests, create a small follow-up instead of asserting all checks passed.

## Delegation policy
Delegate independent read-only review to reviewer; execution belongs to one file owner.

## Done when
A truthful verification matrix, actionable failures, and any unsupported platforms listed.
