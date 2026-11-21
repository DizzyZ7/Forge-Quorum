---
name: concurrency-review
description: Find cross-runtime races, deadlocks, lost updates and retry hazards.
---

# concurrency-review

## Trigger
For concurrent Go/Rust/Java/Kotlin/Node/C#/C++ or queues.

## Procedure
1. Map shared state, locks, ownership, ordering and cancellation.
2. Enumerate failure sequences, retries, shutdown and duplicate delivery.
3. Write a reproducer or stress/race test with bounds.
4. Propose smallest fix preserving interface contracts.
5. Re-run relevant validation and note residual timing risks.

## Delegation policy
Use relevant language specialist, debugger and reviewer.

## Done when
Concrete race/failure scenarios and validated remediation.
