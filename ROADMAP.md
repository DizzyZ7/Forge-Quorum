# ForgeQuorum roadmap

**Delivered through v0.11.0:** 52 engineering role templates, 39 reusable skills, 25 profiles, Codex project installer and plugin exports, offline routing, isolated worktrees, per-job locks, bounded batches, global local-host scheduler, conservative token admissions, cancellation, crash recovery controls, read-only conflict/handoff checks, a repository priority/dependency queue with bounded foreground state observation, and opt-in verified dependency gates with explicit staged committed-patch transfer, declarative task recipes, opt-in quality policies, bounded transition history and static queue dashboards.

## Next priorities (not shipped)

1. **Real Codex runtime integration tests:** run authorized non-production jobs on supported clients and verify the true event/approval lifecycle.
2. **Artifact-aware dependency handoff:** shipped conservative explicit, staged, Git-patch transfer; further work includes richer conflict previews and alternative review workflows.
3. **Queue durability and operator tools:** shipped bounded local event history and offline dashboard; extend with durable archives, richer crash diagnostics and cross-run analytics without a background daemon.
4. **Verified quality gates:** shipped built-in required-gate policies; extend with verified repo-specific gate profiles, trusted execution isolation and provenance attestation.
5. **Accurate resource policy:** account for all executions and model-reported usage with clear partial/missing reporting; no claim of financial caps.
6. **Polyglot build matrix:** actual JS/TS, Go, Rust, JVM, .NET, Swift, Flutter and C++ reproducible examples.
7. **Packaging and developer adoption:** trusted releases, documented installation options, demos and reproducible contribution guides.

## Principles

- Never imply that an agent role template executes by itself.
- Keep run authorization explicit and preserve all user code.
- Dependencies determine ordering until explicitly reviewed code integration exists.
- Do not auto-clear abandoned claims, force-push, merge or deploy.
- Treat a passing Codex invocation as distinct from independent verification.
