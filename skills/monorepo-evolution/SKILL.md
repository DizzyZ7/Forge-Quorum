---
name: monorepo-evolution
description: Make safe cross-package changes in polyglot monorepos.
---

# monorepo-evolution

## Trigger
When changing shared code, workspace tooling or multiple apps.

## Procedure
1. Detect workspace manifests, package boundaries and build graphs.
2. List consumers and API/version compatibility obligations.
3. Plan dependency-aware changes with single-writer interfaces.
4. Run affected package tests and top-level checks.
5. Document any remaining downstream migration requirements.

## Delegation policy
Use repo-explorer, architect and the minimum relevant language implementers.

## Done when
Cross-package change with compatibility and verified coverage.
