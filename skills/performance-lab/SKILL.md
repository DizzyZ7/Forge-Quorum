---
name: performance-lab
description: Measure, optimize and verify real latency/memory/cost bottlenecks.
---

# performance-lab

## Trigger
For slow paths, high load, memory growth or expensive queries.

## Procedure
1. Capture reproducible baseline metrics and workload.
2. Locate hotspots via profiling, tracing or explain plans.
3. State optimization hypothesis and correctness invariants.
4. Apply smallest measurable improvement.
5. Rerun equivalent workload at least twice if feasible.
6. Compare distributions rather than one arbitrary run.
7. Check for new contention, stale cache or elevated resource use.

## Delegation policy
Use performance-engineer plus relevant implementation owner; avoid parallel edits to one hotspot.

## Done when
Before/after measurements, test conditions, known uncertainties and changes.
