# Isolated Codex jobs and bounded batches (v0.6.0)

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
```

The `start` command creates `forgequorum/<id>` from **committed HEAD** in a separate Git worktree at `../.forgequorum-worktrees/<repo>/<id>`. Your uncommitted changes are **never copied or discarded**. If you need project-specific agents and skills in the task's worktree, **commit the installed `.codex/agents/`, `.agents/skills/` and `AGENTS.md` before starting the job**. No secrets or prompts are sent during planning or workspace creation.

`run` without `--execute` is read-only. With `--execute`, it invokes the installed Codex CLI from the worktree with `codex exec --json --sandbox workspace-write`. This may use tokens and edit code. Codex authentication, network use, approvals and sandbox enforcement are outside the Python CLI's control. ForgeQuorum does not save JSONL transcripts, credentials or model messages. Its run metadata includes **the task text you supplied**, so do not put secrets in task descriptions.

## Bounded batch execution

Create a dedicated job for each independent task and confirm the worktrees do not share implementation file ownership.

```bash
fq swarm batch <job-a> <job-b> --target . --max-parallel 2
fq swarm batch <job-a> <job-b> --target . --max-parallel 2 --execute
fq swarm review <job-a> --target . --json
```

Without `--execute`, the batch only validates jobs and returns a preview. On execution it checks up to 12 distinct prepared IDs, then runs at most 4 concurrent Codex processes per CLI invocation. A lock claims each job to guard against duplicate starts. Workers retain their own failure records and worktrees for review. The read-only `swarm review` summarizes Git status and tracked diffs but cannot certify correctness. **No automatic merge, push or deploy.**

There is no global process cap, no money/token budgeting, cancellation API or safe automatic recovery for abandoned locks. On a crash, inspect any leftover `running` metadata, lock file and active processes before manual intervention. Process timeouts cannot guarantee cleanup of child processes on every platform.

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

- One Codex process per job; an explicit batch may launch distinct jobs in parallel, with a per-batch limit but no global scheduler.
- Source/code review, tests and merges are not automatic proof of correctness. Check actual outputs and Git status.
- Codex subagent invocation is advisory and client-dependent, not guaranteed.
- `--timeout` limits waiting for the direct Codex process; child process behavior depends on the operating system and Codex runtime.
- A crashed process may leave a `running` record and exclusive lock requiring manual inspection. No automatic force-recovery is attempted.
- Worktrees start from committed HEAD: local uncommitted changes are not included.
- If a test process modifies external systems, worktree isolation does not stop those effects.
