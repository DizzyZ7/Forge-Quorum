---
name: build-feature
description: Deliver a feature end-to-end from scope and design through code, tests and review.
---

# build-feature

## Trigger
For multi-file, user-facing or backend feature requests.

## Procedure
1. Define the user journey and measurable acceptance criteria.
2. Inspect existing entry points and contracts before proposing a design.
3. Produce a minimal dependency-aware plan and isolate independently editable areas.
4. Implement in thin vertical slices with tests and clean rollback boundaries.
5. Ask security-auditor for review if auth, data or untrusted input is involved.
6. Use reviewer independently after implementation where possible.
7. Run repository-specific test/lint commands and report actual output.
8. Summarize files changed, behavior shipped, known risks and next steps.

## Delegation policy
Use product-analyst/architect only if scope or architecture is genuinely unclear; do not fan out by default.

## Done when
Acceptance criteria demonstrably met, no secret exposure, regression tests run, limitations explicit.
