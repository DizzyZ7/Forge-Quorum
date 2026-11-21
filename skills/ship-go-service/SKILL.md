---
name: ship-go-service
description: Ship a Go service with cancellation, race and contract checks.
---

# ship-go-service

## Trigger
For Go microservices, workers and network tools.

## Procedure
1. Inspect go.mod and existing package boundaries.
2. Propagate contexts and handle resource shutdown.
3. Check races, deadlines, interfaces and compatibility.
4. Run go test and race checks when available.
5. State operational rollout and monitoring impact.

## Delegation policy
Use go-engineer, test-engineer and optional reviewer.

## Done when
Verified Go build/tests and a concurrency-risk summary.
