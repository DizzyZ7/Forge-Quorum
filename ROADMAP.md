# ForgeQuorum roadmap

**Shipped through v0.8.0:** 52 role definitions, 39 skills, 25 profiles, plugin exports, offline stack/routing/verification, local context checkpoints, opt-in `codex exec` jobs, isolated Git worktrees, per-job cross-process claims, bounded parallel batches, read-only review reports, cross-process admission slots, conservative token reservation ledger, and manual handoff preflight. Real subagent scheduling remains a Codex runtime responsibility.

## Next priorities (not shipped)

1. **Stack adapters:** project-specific test/build commands for JS/TS, Go, Rust, Java, C#, Flutter, PHP and C++ with a user-reviewed plan and explicit execution authorization.
2. **Composite profiles:** support multi-package repositories without installing a huge `full` profile; selectable role sets, multiple matching stacks and exact manifests.
3. **Advanced orchestration:** optional Codex SDK/app-server integration for streaming events, richer runtime event streaming, permission propagation, and safe crash recovery.
4. **Execution budgets:** live token controls (not just admission reservations), measured execution traces and human checkpoints.
5. **Worktree coordination:** expand read-only Git summaries into ownership-aware diff review, merge previews and conflict handling.
6. **Quality gates:** verified build/test/static/security results, provenance, baseline snapshots and rollback plans.
7. **Packaging and discovery:** signed cross-platform binaries, verified installation paths, demos and contribution templates.

## Principles

- Keep offline configuration and actual agent execution separate; never imply that a generated TOML file executed an agent.
- Prefer fewer capable specialists to unbounded fan-out.
- Never run newly detected commands or apply infrastructure changes automatically.
- Preserve existing user files and reject unsafe conflicts.
- Support more languages by meaningful, tested behavior—not a marketing count alone.

### Delivered in v0.7.0

- Cooperative cancellation with explicit opt-in and preserved worktree edits.
- Safe, operator-confirmed interrupted-job recovery without deleting run locks.
- Git path overlap reports, per-worktree verification plans/results and usage summaries based only on reported Codex tokens.

### Remaining priorities

- Extend per-user scheduling to optional cross-host coordination, audit trails and stronger runtime cost enforcement.
- Better observability, audit history and safe resume semantics for interrupted jobs.
- Stronger end-to-end Codex live-runtime testing and operating-system child-process verification.
- Explicit, reviewable patch reconciliation without default automatic merges.

### Delivered in v0.8.0

- Per-OS-user global scheduler slots across CLI processes with explicit, fail-closed stale-claim handling.
- Optional daily UTC reservation accounting and manual ticket release; not a billing guarantee.
- Conservative read-only multi-job handoff gate; still no autonomous merging.
