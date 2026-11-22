# Changelog

## 0.11.0 — Declarative task DAGs, quality policies and offline dashboard

- Added `fq workflow RECIPE` preview and explicit `--apply` queue preparation for up to 12 reviewed, ordered tasks with symbolic predecessors, profiles, priorities and dependency gates.
- Added failure-safe partial-apply reporting that preserves existing worktrees and returns actual created job IDs rather than silently resetting user changes.
- Added optional `forgequorum.quality.json` required-test policy using an allowlist of existing detected verification gates; no arbitrary shell commands, no automatic test execution.
- Added an atomic, bounded 500-event queue transition history and `fq queue events` with no prompts or agent transcripts.
- Added a read-only `fq queue dashboard` status projection and opt-in, static, escaped HTML export to a new output file.
- Added original workflow examples, documentation and regression tests on disposable Git repositories. Live model execution is still unverified.


## 0.10.0 — Verified dependency gates and explicit patch handoff

- Added optional `fq queue add --gate verified|transferred` admission policies. The backward-compatible default remains `order`.
- Strict dependencies require successful and still-fresh test evidence for each completed, clean parent commit. Changed, dirty or unverified parents block downstream admission.
- Added `fq queue transfer CHILD --from PARENT` to preflight committed Git patches, and `--apply` to stage accepted changes only in the dependent worktree. No merge, automatic commit, reset, push or deployment.
- Added conflict, stale-index, path, symlink, submodule, patch-size and provenance safety checks, including multi-dependency handoffs with non-overlapping paths.
- Added regression tests with real temporary Git worktrees, binary patches, legacy v0.9 queue records and CLI dry-runs. This does **not** imply live Codex model integration was tested.

## 0.9.0 — Repository priority queue and dependency ordering

- Introduced repository-scoped `fq queue add/status/run/priority/retry/cancel/recover/watch` with persistent metadata and atomic selection across independent CLI invocations.
- Added -100..100 priority ordering, FIFO tie-breaks and creation-time dependencies on existing queued jobs, avoiding dependency cycles.
- Dependent execution waits for successful Codex invocation; failed/cancelled predecessors block downstream work. Worktree content is never automatically transferred or merged.
- Dispatch is preview-only by default; explicit `--execute` and local scheduler admission still control actual model execution.
- Implemented fail-closed abandoned claims, confirmation-gated operator recovery and conservative queue metadata validation.
- Added bounded foreground JSONL observation of changing queue states (not model transcripts), safe cancellation of waiting entries, and regression coverage across real Git worktrees and independent processes.
- No background daemon, automatic verification, code merge, billable-token cap or remote scheduler.

## 0.8.0 — Cross-process admission and safe handoff

- Added local-host global Codex process admissions, configurable concurrent jobs and conservative daily token reservations.
- Added operator-confirmed dead-PID scheduler ticket recovery and read-only `swarm handoff` to assess recorded verification, changed paths and branch conditions before manual integration.
- Reservations are not a hard resource or billing cap; semantic merge safety is not guaranteed.


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
