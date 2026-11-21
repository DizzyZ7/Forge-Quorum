---
name: repair-bug
description: Reproduce and fix a bug with a regression test and verified root cause.
---

# repair-bug

## Trigger
When asked to troubleshoot errors, crashes, flaky behavior or unexpected results.

## Procedure
1. Capture observed symptoms, environment and expected behavior.
2. Identify smallest reproduction; preserve existing failing logs safely.
3. Trace the affected path; isolate the earliest causal violation.
4. Make a test fail before changing code when feasible.
5. Implement the smallest robust correction, avoiding unrelated refactors.
6. Run the test again and relevant surrounding tests.
7. Document whether the root cause was confirmed or remains a hypothesis.

## Delegation policy
Bring in debugger; ask another agent for independent review only on a high-risk fix.

## Done when
Repro, cause, fix, regression proof and any tests not run.
