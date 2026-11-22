# ForgeQuorum: declarative workflows and offline monitoring

`fq workflow` provides a **preview-first task planner** for a Git repository. It expands
user-authored JSON into separately reviewable worktree jobs. It never calls Codex;
execution still requires an explicit `fq queue run --execute`.

## Recipe format (schema 1)

Use [the original full-stack recipe](../examples/workflows-fullstack.json) as a starting point.
Each step accepts `key` (unique lowercase identifier), `task`, `profile`, `priority`
(-100..100), `max_agents` (1..6), `after` (keys of **earlier** steps), and `gate`
(`order`, `verified`, `transferred`). A strict gate requires at least one dependency.
The recipe is limited to 12 steps and 64 KiB. Unknown fields, unknown profiles,
forward references and invalid dependencies fail before worktree creation.

```bash
fq workflow ./examples/workflows-fullstack.json --target /path/to/git/repo
fq workflow ./examples/workflows-fullstack.json --target /path/to/git/repo --apply
fq queue status --target /path/to/git/repo
fq queue run --target /path/to/git/repo         # preview only
fq queue run --target /path/to/git/repo --execute  # explicitly run Codex
```

`--apply` creates each job sequentially, replacing symbolic predecessor keys with
actual job IDs. If disk, Git or queue registration fails in the middle, already
created worktrees remain untouched and the error includes the completed key-to-ID
map. **Do not rerun blindly:** inspect `fq queue status` first; no rollback of
user-visible Git worktrees is performed. Parallel agents do not share uncommitted
changes. An `order` gate does not copy code; verified or transferred gates follow
the manual procedures in [ORCHESTRATION.md](ORCHESTRATION.md).

## Repository quality policy

The optional root-level `forgequorum.quality.json` is an explicitly committed,
declarative file. See [the example policy](../examples/quality-policy.json):

```json
{"schema": 1, "required_gates": ["go-test"]}
```

Supported names are `go-test`, `cargo-test`, `python-unittest`, `js-test`,
`maven-test`, `gradle-test`, `swift-test`, `dart-test` and `ruby-test`.
Unknown names, duplicates and arbitrary shell commands are rejected. The
policy does **not** run any commands by itself. `fq verify` previews the detected
gates and marks missing requirements; `fq verify --run` executes only the
previously supported, known argument-array test commands. A missing or failing
required test makes the result unsuccessful and prevents a new `verified`
dependency admission when the recorded verification is unsuccessful.

Review every proposed command before using `--run`: the project test scripts
are not sandboxed by ForgeQuorum. This policy does not add custom commands,
coverage percentages, security scans, billing controls or remote attestations.

## Observability without transcripts

```bash
fq queue events --target . --limit 30
fq queue dashboard --target .
fq queue dashboard --target . --html ./forgequorum-dashboard.html
```

The queue's bounded 500-entry **event history** is stored atomically inside the
same private Git queue metadata. Events contain only timestamp, job ID and
transition kind (queued, claimed, completed, failed, cancelled, retried,
reprioritized, recovered, transferred). Legacy queues without `events` remain
readable. The history is a local operational aid, not an immutable audit log.

`dashboard` produces a JSON snapshot with ready, blocked and completed counts.
The optional HTML export writes a **new** static file, refuses overwrites,
escapes user-controlled fields and has no scripts, server, background watchers
or external assets. It does not include the agent's prompt or transcript.

## Operational boundaries

No automatic merge, commit, push or deployment. No unattended background
processes or cross-machine coordination. A successful Codex job is not proof
of passing tests or correct software. Review manual Git changes and verification
evidence before admitting downstream work.
