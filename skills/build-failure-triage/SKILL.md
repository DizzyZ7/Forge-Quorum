---
name: build-failure-triage
description: Isolate failures in compilers, CI, package managers and build pipelines.
---

# build-failure-triage

## Trigger
Use when local or CI builds fail in any supported language or toolchain.

## Procedure
1. Capture the first real error with tool version, command and environment.
2. Separate dependency/environment failures from product code regressions.
3. Choose the smallest reversible fix; avoid broad dependency upgrades.
4. Check clean/dirty worktrees and preserve unrelated work.
5. Rerun the exact failed command and a focused regression test.

## Delegation policy
Use debugger plus the language-specific specialist; security reviewer for supply-chain changes.

## Done when
Verified root cause, scoped patch and evidence of rerun (or a clear blocker).
