# Architecture and trust model

## Components

- **CLI installer** (`src/forgequorum/cli.py`): deterministic preflight, atomic file replacement, manifest, doctor and uninstall.
- **Content registry** (`src/forgequorum/registry.py`): independent, original role and workflow definitions.
- **Codex runtime** (external): reads `.codex/agents`, `.agents/skills`, `AGENTS.md` and trusted `.codex/config.toml`; executes agents when appropriate.
- **Orchestration policy** (`route-task` skill): planning and fan-out recommendations to Codex.
- **Isolated job runner** (`src/forgequorum/swarm.py`): opt-in `codex exec`, Git worktree creation, private job metadata, non-destructive review/cleanup, per-job locks and bounded worker pool; no coordinator daemon.

## Agent lifecycle

1. Main Codex analyzes requested change and identifies independent work.
2. For ambiguous tasks, ask `repo-explorer`, `planner`, or `architect` to collect evidence.
3. Create an explicit contract for each implementer: owned files, inputs, acceptance criteria, and verification.
4. Spawn a small set of independent subagents if the client supports it.
5. The parent reconciles outputs and runs tests. Independent review is evidence-based.
6. Main Codex returns changes, actual checks, and known limitations.

## Security assumptions

Agent instructions are untrusted input to the model execution context; they **do not** enforce filesystem isolation. Always rely on actual Codex sandbox/permission controls. MCP connectors may grant broader privileges, and must be configured and approved by the user. No plugin or connector is installed by this project.

Ordinary CLI commands do not run project code or use network APIs. Explicit `fq verify --run`, `fq swarm run --execute`, and `fq swarm batch --execute` **do** run external commands and must be reviewed. The runner does not store raw Codex transcripts or authentication credentials. The manifest includes hashes, file paths and package version only; it does not include existing project instructions. Collisions halt installation.

See [ORCHESTRATION.md](ORCHESTRATION.md) for Git worktree isolation and runtime trust limits.

## Compatibility surface

The project targets official Codex custom agent TOML, the agent skills folder convention, repo `AGENTS.md`, and `[agents]` configuration. Changes in client behavior may require a future compatibility release. The fallback for an unavailable subagent capability is sequential execution of the workflow by the main Codex.

## Performance principle

A trivial task should use zero extra agents. A typical cross-cutting feature should require only two to four specialized agents, not all twenty. Parallelism can reduce wall-clock duration only for truly independent tasks and may increase total token usage.

## v0.7 operational controls

`src/forgequorum/swarm_control.py` implements read-only cross-worktree path reports, explicit test gates, last-run JSONL token summaries, cooperative cancel requests and conservative recovery. `swarm.py` owns process startup/termination and job locks. The unit of isolation remains a Git worktree, **not** a security sandbox for tools, hooks, tests or external services. No unattended merge, deploy or process recovery is attempted.
