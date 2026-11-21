# ForgeQuorum roadmap

**Shipped through v0.6.0:** 52 role definitions, 39 skills, 25 profiles, plugin exports, offline stack/routing/verification, local context checkpoints, opt-in `codex exec` jobs, isolated Git worktrees, per-job cross-process claims, bounded parallel batches, and read-only review reports. Real subagent scheduling remains a Codex runtime responsibility.

## Next priorities (not shipped)

1. **Stack adapters:** project-specific test/build commands for JS/TS, Go, Rust, Java, C#, Flutter, PHP and C++ with a user-reviewed plan and explicit execution authorization.
2. **Composite profiles:** support multi-package repositories without installing a huge `full` profile; selectable role sets, multiple matching stacks and exact manifests.
3. **Advanced orchestration:** optional Codex SDK/app-server integration for streamed events, global concurrency enforcement, cancellation, permission propagation and crash recovery.
4. **Execution budgets:** token/runtime caps, cancellation, measurable traces and human checkpoints.
5. **Worktree coordination:** add ownership-aware diff review, merge previews and conflict handling to the shipped isolated job foundation.
6. **Quality gates:** verified build/test/static/security results, provenance, baseline snapshots and rollback plans.
7. **Packaging and discovery:** signed cross-platform binaries, verified installation paths, demos and contribution templates.

## Principles

- Keep offline configuration and actual agent execution separate; never imply that a generated TOML file executed an agent.
- Prefer fewer capable specialists to unbounded fan-out.
- Never run newly detected commands or apply infrastructure changes automatically.
- Preserve existing user files and reject unsafe conflicts.
- Support more languages by meaningful, tested behavior—not a marketing count alone.
