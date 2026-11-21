# ForgeQuorum — capabilities and limitations

This document describes **ForgeQuorum itself**. Features marked as planned are not implemented. Tests validate package structure and offline behavior; they do not prove full production agent orchestration.

| Area | Available today | Limitations |
|---|---|---|
| Specialist roles | 52 Codex custom-agent TOML definitions | Installed with `fq init`; each role is an instruction set, not a separately trained model |
| Reusable skills | 39 project skills plus portable plugin exports | Actual invocation and subagent support depend on the Codex client |
| Plugin distribution | `plugin.json` and `.agents/plugins/marketplace.json` | Live installation compatibility matrix is still pending |
| Task routing | Deterministic offline `fq recommend` and profile selection | No LLM scheduler, token spending, or autonomous execution |
| Repository inspection | Bounded filename-based `fq inspect` | Does not parse source code or guarantee correct stack detection |
| Project integration | SHA-256 manifests, conflict protection and managed `AGENTS.md` block | Existing user-managed files are never silently replaced |
| Verification | Read-only `fq verify` plans with explicit `--run` execution | User-defined test scripts may have side effects; not a security sandbox |
| Local context | `fq context` summarizes stack metadata; `fq checkpoint` writes opt-in notes | No automatic transcript capture or cross-session learning |
| Hooks | Optional example for an advisory Codex session-start hook | Requires explicit configuration and trust; not part of plugin distribution |
| Quality | Unit tests, portable exports checked in CI, routing fixtures | No real multi-language end-to-end Codex task matrix yet |
| Isolated Codex jobs | `fq swarm` plans, creates dedicated Git worktrees, optionally invokes `codex exec` and preserves reviewable Git branches | Optional bounded batch execution of prepared jobs, max 4 processes per batch; Codex-native subagent delegation is advisory. No global concurrency limit, merges or production deploys. v0.7 adds explicit cancellation, interrupted-state recovery, worktree path overlap reports, test gates and partial reported-token telemetry |
| Cost controls | Explicit `--execute`, per-job timeout and per-batch concurrency cap | Reported per-run token counts and a cross-job summary; no account-wide billing, hard spend cap, or guaranteed termination of all child processes |
| Deployment | Review-first release and rollout guidance | No unattended deploys, cloud mutations or destructive production commands |

## Installation and verification

For project-specific roles and skills:

```bash
python -m pip install --upgrade "git+https://github.com/DizzyZ7/Forge-Quorum.git"
fq init --target ./my-project --profile auto --dry-run
fq init --target ./my-project --profile auto
fq doctor --target ./my-project
```

For development of ForgeQuorum itself:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python tools/sync_skills.py --check
python tools/evaluate_routing.py
```

## Design priorities

- Publish only features that actually work; distinguish configuration from execution.
- Preserve explicit user approval for executing project code or changing production systems.
- Prefer deterministic and low-cost inspection over unnecessary AI calls.
- Favor portable, original documentation and compatibility with native Codex interfaces.
- Maintain release notes and user examples against actual tested behavior.

[Orchestration guide](ORCHESTRATION.md) · For upcoming features, see [ROADMAP.md](../ROADMAP.md).
