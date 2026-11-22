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
| Isolated Codex jobs | `fq swarm` plans, creates dedicated Git worktrees, optionally invokes `codex exec` and preserves reviewable Git branches | Optional bounded batch execution of prepared jobs, max 4 processes per batch; Codex-native subagent delegation is advisory. Global local-host admission is now available through `fq scheduler`; still no automatic merges or production deploys. v0.7 adds explicit cancellation, interrupted-state recovery, worktree path overlap reports, test gates and partial reported-token telemetry |
| Cost controls | Explicit `--execute`, per-job timeout and per-batch concurrency cap | Reported token counts, global local-host process admission and conservative token reservations; no account-wide billing, hard spending cap, or guaranteed termination of all child processes |
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


## v0.8.0 additions

| Area | Available | Limitation |
|---|---|---|
| Global process admission | `fq scheduler` coordinates ForgeQuorum Codex runs for one OS user | Does not observe unrelated clients, hosts or users |
| Token reservations | Optional UTC daily token reservation ledger, reconciled to reported usage | Not a real-time hard cap, actual billing, or a pricing estimator |
| Safe handoff | `fq swarm handoff` checks completed jobs, verification freshness, clean commits, base divergence and overlapping paths | Advisory only; cannot rule out semantic conflicts or merge automatically |
| Recovery | Operator-confirmed global ticket release after PID exit | Does not kill processes, remove job locks or refund unknown usage |


## v0.9.0 priority queue

| Capability | Available now | Limitation |
|---|---|---|
| Priority dispatch | `fq queue add`, `status`, `run` prioritize existing worktree jobs (-100..100) | Only tasks created in this repository queue; bounded 12 jobs per command |
| Dependencies | Execution-order `--after` on previously queued IDs, with blocked/failed state | Changes are **not** copied or merged across worktrees; completed jobs are not automatically verified |
| Multi-CLI claims | Atomic repository-scoped queue mutex, persistent per-job claims | Crashes require human recovery and separate scheduler inspection |
| Observation | Bounded foreground `fq queue watch` emits changed local metadata as JSONL | No model transcript streaming, daemon or remote event service |
| Recovery/control | `queue retry`, `cancel`, `recover`, `priority` require explicit confirmation | Never deletes user edits or terminates unrelated processes |

## v0.10.0 — quality-gated dependencies and staged transfers

| Capability | Available | Boundary |
|---|---|---|
| Verified queue dependencies | `fq queue add --gate verified --after ...` checks fresh clean parent commit and passing recorded tests | Requires explicitly executed `swarm verify --run` after committing; not an autonomous test runner |
| Patch-aware queue dependencies | `--gate transferred` refuses downstream admission until every parent has been verified and explicitly transferred | Existing v0.9 `order` remains default; no change to legacy behavior |
| Git patch preview and staging | `fq queue transfer CHILD --from PARENT [--apply]` checks and then stages committed parent changes into child worktree | No merge/commit/push/deploy; rejects conflicts, unsupported paths, edited worktrees, symlink/submodule changes, large patches |
| Transfer provenance | Records SHA-256 of patch and staged index, parent and destination Git HEADs | Local records are not remote attestations and cannot detect authorized arbitrary edits outside the tool |

## v0.11.0 — workflow and quality planning

| Area | Available now | Boundary |
|---|---|---|
| Declarative plans | `fq workflow RECIPE [--apply]` previews and queues up to 12 ordered, dependent tasks | No LLM planning or automatic rollback of partially created Git worktrees |
| Quality policies | Optional root-level `forgequorum.quality.json` requires known test gates | No custom shell commands, guaranteed sandbox, or remote proof of test success |
| Queue events | Bounded 500-entry history in atomic queue metadata; `fq queue events` | Local operational history, not an immutable audit log or agent transcript |
| Queue dashboard | `fq queue dashboard` JSON view and explicit static HTML export | No live server, background service, remote tracking or browser-side scripts |

[Workflow usage and constraints](WORKFLOWS.md).
