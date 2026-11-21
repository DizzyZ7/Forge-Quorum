---
name: test-driven-loop
description: Develop a behavior change through reproducible red-green-refactor tests.
---

# test-driven-loop

## Trigger
Use for nontrivial bugs and features where an automated regression can be written.

## Procedure
1. Identify precise observable behavior and one negative counterexample.
2. Write a failing test and run it; if unable, report the limitation instead of claiming RED.
3. Implement only enough code to satisfy the behavior, preserving compatibility.
4. Run the focused test and then broader affected suites; report actual evidence.
5. Refactor with tests unchanged and re-check regressions.

## Delegation policy
Use test-engineer for specification and implementation specialist for the fix; avoid overlapping edits.

## Done when
A reproducible failing-before/passing-after test and explicit remaining risks.
