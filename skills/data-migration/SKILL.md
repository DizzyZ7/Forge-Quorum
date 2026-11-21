---
name: data-migration
description: Plan and safely validate SQL/schema/data migrations including rollback.
---

# data-migration

## Trigger
When moving data, adding columns, changing indexes or backfilling production datasets.

## Procedure
1. Enumerate schemas, data volume, constraints and dependencies.
2. Choose expand/migrate/contract where zero-downtime compatibility matters.
3. Design idempotent backfills, batching, transaction scope and checkpoints.
4. Consider concurrent writes, locks, index build and rollback feasibility.
5. Trial migration in a representative non-production environment.
6. Produce exact preflight/verification checks and monitoring.
7. Never execute destructive production DDL without explicit authorization.

## Delegation policy
Use database-engineer and security-auditor as needed; no autonomous production changes.

## Done when
Migration, validation queries, abort criteria and rollback strategy.
