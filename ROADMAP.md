# ForgeQuorum roadmap

**Delivered through v0.9.0:** 52 engineering role templates, 39 reusable skills, 25 profiles, Codex project installer and plugin exports, offline routing, isolated worktrees, per-job locks, bounded batches, global local-host scheduler, conservative token admissions, cancellation, crash recovery controls, read-only conflict/handoff checks, and a repository priority/dependency queue with bounded foreground state observation.

## Next priorities (not shipped)

1. **Real Codex runtime integration tests:** run authorized non-production jobs on supported clients and verify the true event/approval lifecycle.
2. **Artifact-aware dependency handoff:** explicitly reviewed patch transfer or cherry-pick into dependent worktrees, with conflict previews; never silently merge.
3. **Queue durability and operator tools:** audit event history, status snapshots, safe recovery guidance, no background execution by default.
4. **Verified quality gates:** support optional dependency policies requiring fresh commit/test evidence before dispatch.
5. **Accurate resource policy:** account for all executions and model-reported usage with clear partial/missing reporting; no claim of financial caps.
6. **Polyglot build matrix:** actual JS/TS, Go, Rust, JVM, .NET, Swift, Flutter and C++ reproducible examples.
7. **Packaging and developer adoption:** trusted releases, documented installation options, demos and reproducible contribution guides.

## Principles

- Never imply that an agent role template executes by itself.
- Keep run authorization explicit and preserve all user code.
- Dependencies determine ordering until explicitly reviewed code integration exists.
- Do not auto-clear abandoned claims, force-push, merge or deploy.
- Treat a passing Codex invocation as distinct from independent verification.
