# ForgeQuorum roadmap

## Shipped in v0.4.0

- Independently authored Codex Agent Plugins package with synchronized skills.
- Project-scoped agent installation, role/stack routing, checkable offline routing fixtures.
- Read-only, multi-language test plans and explicitly authorized execution.
- Local file-name context summaries and opt-in private checkpoints; opt-in SessionStart template.

## Next milestones — NOT implemented

1. End-to-end plugin installation smoke tests in supported Codex CLI/desktop versions, with version matrix and compatibility report.
2. Robust opt-in lifecycle hook library with explicit trust review, bounded outputs, cross-platform testing.
3. Persistent workflow state and human-reviewed memory/lesson promotion, no automatic transcript harvesting.
4. Agent scheduler with Codex-backed real execution, strict file ownership and isolated git worktrees.
5. Evidence-based eval harness for whole multi-agent runs and measured token/cost budget (requires approved runtime integration).
6. Language-specific verification presets covering more frameworks and SDKs, without arbitrary command injection.
7. Public plugin submission preparation, policy review, security checks, demo project and installation docs.

## Principles

- Portability across languages and operating systems, not Python-only development.
- Never confuse an agent configuration with a separately trained model or an executing worker.
- No surprise side effects: dry-run/planning by default, opt-in execution and deployment.
- Honest verification: only call a check passed when it actually ran.

