# Changelog

## 0.8.0 — Cross-process scheduler and conservative handoff

- Added global per-user Codex admission slots across ForgeQuorum CLI invocations with fail-closed, manually recoverable claims.
- Added opt-in UTC daily token reservation ledger and conservative reconciliation based on Codex-reported totals; not a live or monetary cap.
- Added `fq scheduler status/configure/release` with explicit confirmations and process-owner checks before manual release.
- Added `fq swarm handoff` for read-only clean-worktree, verification, base-head and path-overlap preflight. No automatic merges.
- Added cross-process and concurrency regression tests; no transcriptions, auto-push, background daemon or external service.


## 0.7.0 — Operational controls and evidence-based verification

- Added `fq swarm cancel` with explicit confirmation, cooperative interruption and preservation of worktree changes.
- Added `fq swarm recover` for explicitly marking jobs with missing locks as interrupted; active or abandoned locks are never deleted.
- Added `fq swarm conflicts` for read-only NUL-safe Git path overlap checks across 2–12 worktrees, including committed and untracked files.
- Added `fq swarm verify` with preview-first, opt-in worktree test execution and status-only verification records.
- Added `fq swarm usage` with available JSONL-reported input/cached/output token aggregates and honest missing/partial coverage. No token-cost estimates or spending limits.
- Codex task prompts are now sent via stdin instead of command-line arguments.
- Added regression tests including a POSIX process-cancellation smoke test, lock safety, recovery, path collisions and usage reports.
- Automatic retry, merge, push, deployment, exact billing and global concurrency caps remain out of scope.


## 0.6.0 — Bounded concurrent Codex jobs and review reports

- Added `fq swarm batch <id>... [--execute] --max-parallel 1..4` for explicit parallel execution of up to 12 already prepared Git worktree jobs.
- Added atomic per-job run claims, second-chance state and branch validation, and refusal to delete abandoned locks automatically.
- Batch preflight rejects invalid, duplicate, missing or non-runnable jobs before starting workers. Each job outcome is reported separately and results remain reviewable after failures.
- Added `fq swarm review <id>` as a read-only Git change summary, without claiming tests have run or a merge is safe.
- Recorded observed run duration in job metadata. No raw Codex transcripts are retained.
- Added regression tests for concurrency caps, duplicate execution, failed workers, branch mismatch, dry-run safety and review reports.
- Still no global concurrency cap, live token/cost quota, automatic merges, deployments or cancellation API.

## 0.5.0 — Isolated Codex jobs (preview)

- Added `fq swarm plan/start/run/status/list/cleanup` to plan specialist teams and prepare reviewable tasks in separate Git worktrees.
- Worktrees use unique `forgequorum/<id>` branches based on committed HEAD; local uncommitted changes remain untouched.
- Real `codex exec` invocation requires explicit `--execute` and uses `--sandbox workspace-write`; no automatic merge/push/deploy.
- State is saved in private Git metadata; CLI retains status/event counts rather than raw Codex transcripts. Cleanup requires `--confirm` and refuses uncommitted/untracked content.
- Added Git fixture regression tests, mocked Codex execution tests and a dedicated orchestration guide.
- Native subagent delegation remains a Codex capability, not a guaranteed multi-agent runtime; concurrency and token telemetry are not yet implemented.

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
