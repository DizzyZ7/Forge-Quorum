# ForgeQuorum

### One prompt. An entire engineering team.

**52 specialist roles · 39 reusable skills · 25 curated profiles · Native Codex integration**

ForgeQuorum is an independent, open-source, polyglot engineering toolkit for Codex: developer roles, reusable skills, safe project installation, deterministic routing and verifiable quality gates.

## Choose your installation method

**Native Codex plugin (skills only):** In a Codex client that supports plugin marketplaces, add the ForgeQuorum marketplace and enable the plugin:

```text
codex plugin marketplace add DizzyZ7/Forge-Quorum
```

Invoke `$route-task`, `$verification-loop`, `$test-driven-loop` or `$context-checkpoint`. Custom subagent roles are **not** installed by the plugin; use the CLI installation below. Live plugin installation has not been confirmed on every Codex client/version.

**Project CLI (agents and skills):**

```bash
python -m pip install --upgrade "git+https://github.com/DizzyZ7/Forge-Quorum.git"
fq inspect --target ./my-project
fq init --target ./my-project --profile auto
fq doctor --target ./my-project
```

Avoid installing the same skill through both methods. Hooks are opt-in and are never silently enabled. `fq verify` proposes commands without running them; `fq verify --run` explicitly executes project-defined code and is **not** a sandbox. See the [capability and limitations inventory](docs/CAPABILITIES.md) and [official Codex plugin documentation](https://developers.openai.com/plugins/build/plugins).

---

> **v0.8.0 adds cross-process scheduling, conservative token reservations, and manual handoff preflight for isolated Codex jobs. It is not an autonomous multi-agent scheduler.** Actual subagent execution is delegated to Codex, subject to client support, sandbox permissions and available tools. Roles are instructions, not separate trained models.

[Русская документация](README.md) · [Language support](docs/LANGUAGE-SUPPORT.md) · [Architecture](docs/ARCHITECTURE.md) · [Roadmap](ROADMAP.md)

## Quick start

Python **3.11+ is only required to run the installer**; your target project may use any language.

```bash
python -m pip install --upgrade "git+https://github.com/DizzyZ7/Forge-Quorum.git"
fq inspect --target ../your-project
fq profiles
fq init --target ../your-project --profile auto --dry-run
fq init --target ../your-project --profile auto
fq doctor --target ../your-project
fq recommend "Implement a Kotlin Ktor API with tests" --target ../your-project --profile auto
```

Open `../your-project` in Codex and ask:

```text
$route-task Implement the requested feature using existing project conventions.
Select only necessary language-specific specialists, assign non-overlapping file
ownership, run the actual build/tests, report evidence and request approval
before publishing or deploying anything.
```

## Isolated Codex jobs with global admission control (v0.8.0)

```bash
fq swarm plan "Build a Go API with tests" --target . --json
fq swarm start "Build a Go API with tests" --target . --json
fq swarm list --target .
fq swarm run <job-id> --target .               # preview, no execution
fq swarm run <job-id> --target . --execute    # explicit Codex invocation
fq swarm status <job-id> --target .
fq swarm review <job-id> --target .          # read-only Git change summary
fq swarm batch <job-a> <job-b> --target . --max-parallel 2          # preview
fq swarm batch <job-a> <job-b> --target . --max-parallel 2 --execute
fq swarm cleanup <job-id> --target . --confirm
```

Every job starts in its own `forgequorum/<id>` branch and Git worktree based on committed HEAD. Your uncommitted changes are not copied or discarded. No automatic merge, push or deployment is performed. Execution requires a locally installed and authenticated Codex CLI and may consume tokens. Parallel batches are limited to four workers per CLI invocation, and a separate cross-process scheduler defaults to two globally admitted Codex processes per user profile. An optional daily *reservation-based admission budget* is available, but it cannot cap real-time usage or guarantee monetary spending. There is no automatic conflict resolution. See the [orchestration guide](docs/ORCHESTRATION.md) for safety, limitations and review workflow.

## Why this approach?

- **Native Codex assets:** `.codex/agents/<role>.toml` plus `.agents/skills/<skill>/SKILL.md`, with a marked block in `AGENTS.md`.
- **Language-specific specialists:** Node.js, JVM, Go, Rust, .NET, C++, mobile, desktop, game engines, data, ML and infrastructure.
- **Adaptive profiles:** 25 curated installation sets and a filename-based `auto` detector. The scanner does not read file contents or execute project commands.
- **Small teams, clear ownership:** `fq recommend` offers a bounded, deterministic suggestion (1–6 roles). Codex decides what actually runs.
- **Safe installation:** local SHA-256 manifest, preflight conflict detection, preservation of existing Codex config and user-modified managed files.

## CLI

```bash
fq list
fq profiles
fq inspect --target PATH --json
fq init --target PATH --profile go [--dry-run]
fq init --target PATH --profile mobile
fq init --target PATH --profile auto
fq init --target PATH --profile full
fq recommend "Build a Rust Tokio worker" --json
fq recommend "Add a backend endpoint" --target PATH --profile auto --json
fq status --target PATH --json
fq doctor --target PATH --json
fq uninstall --target PATH [--dry-run]
```

Stack detection is a **bounded heuristic**: it ignores dependency/build directories, skips symlinks, and looks at filename patterns and manifests. For a mixed monorepo, `backend` or `full` may be more appropriate than `auto`. Python is not required by generated applications or agent roles.

`recommend` uses deterministic offline rules; it neither invokes an LLM nor spawns subagents. The installed profile is recorded in the manifest. To change the profile, uninstall first and handle conflicts if local files were edited.

## Safety and limits

- Installer and scanner make no API requests, install no project dependencies, and do not execute target code.
- Existing `AGENTS.md` text and `.codex/config.toml` remain untouched outside owned sections.
- Read-only role guidance is **not** a security sandbox; Codex controls permissions.
- The manifest is local metadata, **not** a tamper-proof security boundary against an attacker who can edit it.
- Other languages' builds require their SDKs/runtimes and authorized tools. The CI matrix tests this Python CLI and generated files, not actual Codex execution on every stack.
- Publishing, infrastructure apply, production changes and destructive operations must follow the user's approvals.

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md), [ROADMAP.md](ROADMAP.md) and [CHANGELOG.md](CHANGELOG.md). We welcome focused roles, original workflows, portable examples and reproducible regression tests.

If ForgeQuorum helps, consider starring ⭐ the repository.

MIT License. Copyright © 2026 Dimash Janibekov. Independent community project; not affiliated with OpenAI.

## Worktree orchestration controls (v0.8.0)

```bash
fq swarm conflicts <job-a> <job-b> --target . --json  # read-only path overlap report
fq swarm verify <job-id> --target .                    # preview tests
fq swarm verify <job-id> --target . --run              # explicitly execute project-defined tests
fq swarm usage --target . --json                      # last-run reported token counts
fq swarm cancel <job-id> --target . --confirm          # cooperative cancellation
fq swarm recover <job-id> --target . --confirm         # mark orphaned running record interrupted
```

Cancellation is best effort and never removes worktree changes; recovery refuses to clear run locks. Tests may execute untrusted code and require `--run`. Token usage is JSONL-reported, possibly incomplete, and **not a monetary cost estimate**. ForgeQuorum does not auto-retry, merge, publish or deploy changes. See [the orchestration guide](docs/ORCHESTRATION.md).


## Global scheduling, admission budgets, handoff (v0.8.0)

```bash
fq scheduler status
fq scheduler configure --max-running 2 --daily-tokens 100000 --confirm
fq swarm run <job-id> --target . --execute --reserve-tokens 20000
fq swarm batch <job-a> <job-b> --target . --max-parallel 2 --execute --reserve-tokens 20000
fq swarm handoff <job-a> <job-b> --target .
```

The scheduler shares state across independent CLI processes running **under the same OS user and configuration directory** (`~/.forgequorum/scheduler`). Set the absolute `FORGEQUORUM_STATE_DIR` to use another isolated scheduler, including in tests. Only Codex executions started through ForgeQuorum participate in these limits. A positive reservation is mandatory once a daily quota is configured; jobs cannot start if reservations exceed the daily quota. On completion the reservation is reconciled against Codex-reported token usage when available; otherwise the full reservation remains charged. **This is an admission control mechanism, not a real-time token limiter or cost cap.** An execution may exceed its reservation, and the extra usage will be charged to the ledger after the run.

If a process crashes, its global slot remains claimed intentionally. `fq scheduler status` shows the ticket; after verifying that the process has exited, `fq scheduler release <ticket> --confirm` releases it without refunding reserved tokens. This may require separate recovery of the per-job run lock and state. No abandoned lock is cleared automatically. The scheduler cannot coordinate other operating-system users, separate hosts, or Codex sessions started outside ForgeQuorum. See [orchestration](docs/ORCHESTRATION.md).

`fq swarm handoff` is strictly read-only: it requires completed jobs, clean committed worktrees, successful verification recorded against the current HEAD, a matching source base, and no overlapping Git changed paths. It does **not** merge branches, validate full semantic compatibility, or deploy anything.
