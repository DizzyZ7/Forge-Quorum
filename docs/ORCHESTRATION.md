# Isolated Codex jobs, priority queue and review-first operations (v0.9.0)

ForgeQuorum offers **opt-in local execution**, not an autonomous multi-model server. It coordinates one `codex exec` invocation per prepared worktree and suggests Codex-native subagents when those have been configured. Real delegated agent count depends on your Codex client.

## Quick workflow

Run this in a repository with at least one Git commit (Windows PowerShell can use the same commands with `py -m forgequorum`):

```bash
fq swarm plan "Implement a Go HTTP service with tests" --target . --json
fq swarm start "Implement a Go HTTP service with tests" --target . --json
fq swarm list --target .
fq swarm run <job-id> --target .   # preview only
fq swarm run <job-id> --target . --execute --timeout 900
fq swarm status <job-id> --target . --json
fq swarm review <job-id> --target . --json  # read-only tracked diff/status
```

The `start` command creates `forgequorum/<id>` from **committed HEAD** in a separate Git worktree at `../.forgequorum-worktrees/<repo>/<id>`. Your uncommitted changes are **never copied or discarded**. If you need project-specific agents and skills in the task's worktree, **commit the installed `.codex/agents/`, `.agents/skills/` and `AGENTS.md` before starting the job**. No secrets or prompts are sent during planning or workspace creation.

`run` without `--execute` is read-only. With `--execute`, it invokes the installed Codex CLI from the worktree with `codex exec --json --sandbox workspace-write`. This may use tokens and edit code. Codex authentication, network use, approvals and sandbox enforcement are outside the Python CLI's control. ForgeQuorum does not save JSONL transcripts, credentials or model messages. Its run metadata includes **the task text you supplied**, so do not put secrets in task descriptions.

## Bounded parallel batches

First create independent jobs with `swarm start` (one for each non-overlapping task). A batch does **not** create jobs or modify code until you explicitly authorize execution:

```bash
fq swarm batch <job-a> <job-b> --target . --max-parallel 2  # preview
fq swarm batch <job-a> <job-b> --target . --max-parallel 2 --execute
fq swarm review <job-a> --target . --json
```

The batch supports 1–12 distinct IDs with a maximum of 4 concurrent `codex exec` processes **within that one batch**. Jobs are checked up front; no model calls happen if any ID is invalid or not runnable. Each job has an exclusive lock so overlapping shell sessions cannot execute the same task twice. Failures and timeouts are recorded per job, and successful jobs are not discarded when another worker fails. `swarm review` reports worktree Git status, tracked diff statistics, and recorded execution metadata; it **does not** verify code correctness or inspect untracked contents.

**Important:** A per-user global concurrency admission limit is enforced for Codex jobs started through ForgeQuorum. Independent Codex sessions and other OS users are not accounted for. There is **no live token or monetary spending cap**; only optional conservative reservations. A hard crash can leave a persistent `.lock` and/or `running` state; ForgeQuorum deliberately refuses automatic lock deletion. Inspect the process and repository before manual recovery. Long-running child processes may survive a direct process timeout on some platforms. Cancellation requests and explicit interruption recovery are available in v0.7.0; unattended retries are not supported.

## Review and transfer

```bash
fq swarm status <job-id> --target .
git -C ../.forgequorum-worktrees/<repo>/<job-id> diff
# Review, test, commit and merge/cherry-pick manually as appropriate.
fq swarm cleanup <job-id> --target .           # preview only
fq swarm cleanup <job-id> --target . --confirm # clean worktrees only
```

`cleanup` never forces deletion and refuses uncommitted or untracked changes. It retains the branch and does **not** merge, push, publish, deploy or remove branch history. Job metadata is stored inside Git's private common directory under `forgequorum/jobs/` (not in tracked files). Worktree location is deliberately separate from the main working tree. These measures prevent accidental overwrite in ordinary workflows but are **not** a security sandbox against malicious code, plugins or compromised Git hooks.

## Limits

- One Codex process per job; explicit `swarm batch --execute` permits bounded parallel execution across distinct jobs, not autonomous planning or model-managed scheduling.
- Source/code review, tests and merges are not automatic proof of correctness. Check actual outputs and Git status.
- Codex subagent invocation is advisory and client-dependent, not guaranteed.
- `--timeout` limits waiting for the direct Codex process; child process behavior depends on the operating system and Codex runtime.
- A crashed process may leave a `running` record and an exclusive `.lock` requiring operator inspection. No automatic force-recovery is attempted.
- Worktrees start from committed HEAD: local uncommitted changes are not included.
- If a test process modifies external systems, worktree isolation does not stop those effects.

## Cancel, inspect, recover

```bash
fq swarm cancel <job-id> --target .                # preview only
fq swarm cancel <job-id> --target . --confirm      # cancel a prepared job or request a running job to stop
fq swarm status <job-id> --target . --json
fq swarm recover <job-id> --target .               # preview after an interrupted controller
fq swarm recover <job-id> --target . --confirm     # running + missing lock only
```

The running worker checks for a cancellation marker and attempts to terminate its own Codex subprocess; on POSIX it sends a termination signal to the child's process group, with a kill fallback. On Windows it terminates the directly launched process. This is **best effort**, not a guarantee that all grandchildren or external services have stopped. Any edits remain in the worktree. A completed or cancelled job does not automatically restart.

`recover` cannot delete or bypass a `.lock`. If a process crashes without clearing its running state, first inspect OS processes, worktrees and any external effects. Only when the lock is absent does explicit `--confirm` mark the job **interrupted**, preserving existing files. Interrupted jobs are not automatically retried; start a new task or manually review and resume in the worktree. Never manually remove locks until you know their owners are no longer active.

## Detect competing changes

```bash
fq swarm conflicts <job-a> <job-b> --target . --json
```

This read-only command lists overlapping **tracked and untracked file paths**, including worktree edits and commits since each job's original base. It handles spaces and non-ASCII filenames. This is a *path collision* check, not a semantic merge analysis. No overlaps does not imply the two changes can be combined safely; tests and integration review remain necessary. No merge is attempted.

## Quality gates inside the worktree

```bash
fq swarm verify <job-id> --target .                 # preview test commands, no code execution
fq swarm verify <job-id> --target . --run --timeout 120
fq swarm review <job-id> --target . --json
```

When `--run` is supplied, ForgeQuorum executes selected repository-defined test commands in the **job worktree** and stores only their statuses, exit codes, timestamp and Git state at the time, not test output. Missing tools and zero selected gates do not count as success. The procedure refuses running/locked jobs. This **does not sandbox project code**; test scripts can have side effects beyond their worktree. Review the preview before authorizing. Test results are point-in-time and can become stale when files change.

## Reported token usage

```bash
fq swarm usage --target . --json                       # aggregate available last-run counts
fq swarm usage <job-a> <job-b> --target . --json
```

ForgeQuorum parses `turn.completed` JSONL usage events, reporting input, cached input and output tokens. Cached input is a subset of input and is **not** added a second time to total tokens. Jobs with no JSONL usage are explicitly excluded from the sum. A killed or failed run may have partial usage. No monetary pricing, billing API, true account-level totals, or hard token quota is implemented; independent Codex sessions may have usage invisible to this tool. Transcripts are not stored; prompts are supplied via standard input to avoid exposure in command-line arguments.

## Operational cautions

- `--execute`, `--run` and `--confirm` are separate controls. Nothing in a dry run invokes the model or a project's tests.
- Batch parallelism applies to one CLI invocation; separate shells can launch more processes.
- Creating worktrees runs Git commands and can trigger repository Git hooks (subject to the user's Git configuration). It is not a security boundary for untrusted repositories.
- Recovery only corrects ForgeQuorum bookkeeping after human investigation, not running OS processes.
- Manual review and approval remain mandatory for commit, merge, push, deploy or production changes.


## v0.8.0: scheduler and review-only multi-job handoff

```bash
fq scheduler status
fq scheduler configure --max-running 2 --daily-tokens 100000 --confirm
fq swarm run <id> --target . --execute --reserve-tokens 12000 --wait-seconds 30
fq swarm batch <id-a> <id-b> --target . --execute --max-parallel 2 --reserve-tokens 12000
fq swarm handoff <id-a> <id-b> --target . --json
```

The scheduler is a per-user, local-only file state machine. Cross-process admission is protected by atomic directory mutex and conservative reservations. With a daily quota enabled, positive token reservations are required for every launched job. Missing usage telemetry charges the whole reservation; overspend is recorded *after* execution and can prevent future jobs, but there is no live token hard-stop. By default the budget is disabled, while two global process slots are available. Job-level locks and global slots are separate; after a crash, both may require investigation.

Operator recovery: `fq scheduler status` to identify a ticket, check the originating PID and any descendants, then `fq scheduler release <ticket> --confirm` only after the original process is gone. A separate `fq swarm recover` may still be required for job metadata. No recovery action deletes an unrelated worktree.

`fq swarm handoff` is read-only. It blocks worktree handoff if jobs are unfinished, edits are uncommitted, prior verification is absent or stale, project `HEAD` has diverged from the recorded job base, or multiple job diffs touch the same path. A successful preflight is **not** automatic merging and does not prove semantic compatibility.


## Priority queue and dependency ordering (v0.9.0)

Use `fq queue add TASK --priority 0 --target .` to create a worktree and insert it in the repository-scoped queue. `--after <id> [<id> ...]` accepts only already queued IDs in the same repository. This creation-time rule prevents dependency cycles. Higher priority values (-100..100) run first, ties use FIFO insertion sequence. A blocked high-priority task does not prevent its ready predecessors from running.

`fq queue status` shows queue states and readiness; `fq queue watch --seconds 30` polls that metadata and prints JSONL on changes in the **foreground**. No background daemon, model messages, secrets or Codex transcripts are recorded. `fq queue run --max-jobs 4 --parallel 2` is a preview; add `--execute` to authorize jobs, with explicit per-job timeout and token reservation flags. Admission also obeys `fq scheduler` global limits. Two distinct CLI processes cannot claim one queued job simultaneously.

A dependency is satisfied when a prior queue job's Codex invocation finishes successfully. This **does not** mean its code was merged, tested, reviewed, or made visible in dependent worktrees. Every worktree branches from committed HEAD at *enqueue time*; use an explicit human-reviewed handoff to integrate actual changes.

A failed task blocks its dependents; operator can inspect and explicitly call `fq queue retry JOB --confirm` if its worktree is runnable. `fq queue cancel JOB --confirm` only affects queued (not claimed/running) entries. `fq queue recover JOB --confirm` marks an abandoned claim failed **only if the claiming PID is no longer alive**; operators must also inspect child processes and the global scheduler reservation manually. Claims are never silently reaped. Queue data is in `.git/forgequorum/queue.json` and is not a security boundary against a local attacker with write access.

**Limitations:** no automatic resumption after process crash, no artifact transfer between dependent jobs, no remote host coordination, no hard token or monetary cap, no automatic verification/merge, and no semantic conflict guarantees. `watch` provides state changes, not streaming Codex output.
