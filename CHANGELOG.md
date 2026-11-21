# Changelog

## 0.6.0 — Bounded concurrent Codex jobs and review reports

- Added `fq swarm batch <id>... [--execute] --max-parallel 1..4` for up to 12 already prepared worktree jobs, with all-job preflight.
- Added atomic per-job run locks and branch validation; stale locks require human inspection.
- Added `fq swarm review <id>` for read-only tracked diff statistics and Git status.
- Per-job execution duration and failure outcomes are recorded without raw model transcripts.
- No automatic merges/deploys, cancellation API, global resource caps or live cost accounting.

## 0.5.0 — Isolated Codex jobs

- Added `fq swarm plan/start/run/status/list/cleanup` and isolated Git worktrees.
- Launching Codex requires explicit `--execute`; cleanup requires `--confirm` and a clean worktree.
- Independent agent delegation remains client-dependent.

## 0.4.0 — Native Codex plugin and evidence-first workflows

- Portable Agent Plugins `plugin.json`, local Git-backed repository marketplace, 39 exported skills with reproducible sync checks and selected Codex UI metadata.
- Added five original skills: test-driven-loop, verification-loop, context-checkpoint, build-failure-triage, continuous-improvement.
- Added `fq verify` conservative multi-language test-plan mode (`--run` explicitly required to execute), `fq context`, opt-in `fq checkpoint`, and advisory `fq hook-context` for manually configured SessionStart hooks.
- Added offline 15-fixture routing evaluation suite, independently maintained capability inventory, plugin and safety regression coverage.
- CI verifies committed plugin skills are in sync and validates read-only gate planning.
- No automatic deployment, network dependency install, secret collection, token-cost tracking or arbitrary parallel agent runtime included.


## 0.3.0 — Polyglot expansion

- Expanded from 20 to **52** specialist roles and from 14 to **34** workflow skills, including JVM, Go, Rust, C/C++, .NET, mobile, desktop, games, cloud, data/ML and functional/scientific ecosystems.
- Added **25 curated profiles** covering language stacks and engineering domains; kept the existing profile names for backward compatibility.
- Added bounded, offline filename-based `fq inspect --target PATH [--json]`, with ignored generated directories and symlink skipping.
- Added `fq init --profile auto` to select and store a concrete profile from project markers.
- Added context-aware `fq recommend ... --target PATH [--profile auto]` and explicit language-specialist overrides to avoid assigning Python to unrelated projects.
- Added cross-language regression fixtures and documentation for native toolchain boundaries.
- Existing v0.1/v0.2 installation manifests remain supported; no automatic profile switch, no execution of user code, no external API calls.

## 0.2.1 — Windows fixes

- Fixed Windows-specific compatibility issues and added regression checks.

## 0.2.0 — Profiles and offline routing

- Added curated profiles, deterministic recommendations, status JSON, manifest allowlisting and additional regression tests.

## 0.1.0 — First preview

- Initial Codex-native role pack, reusable skills and safe installer.
