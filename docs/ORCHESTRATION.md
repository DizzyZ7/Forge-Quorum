# Isolated Codex jobs (v0.5.0 preview)

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

- One Codex process per job; multiple jobs can be started independently but are not auto-scheduled in parallel.
- Source/code review, tests and merges are not automatic proof of correctness. Check actual outputs and Git status.
- Codex subagent invocation is advisory and client-dependent, not guaranteed.
- `--timeout` limits waiting for the direct Codex process; child process behavior depends on the operating system and Codex runtime.
- A crashed process may leave a `running` record requiring manual inspection. No automatic force-recovery is attempted.
- Worktrees start from committed HEAD: local uncommitted changes are not included.
- If a test process modifies external systems, worktree isolation does not stop those effects.
