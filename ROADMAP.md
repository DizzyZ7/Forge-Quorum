# Roadmap / План развития

## v0.1.0 — shipped locally

- [x] 20 domain-specific native Codex subagents
- [x] 14 reusable workflow skills with delegation and completion criteria
- [x] Project-scoped safe installer with dry-run, SHA-256 manifest and uninstall
- [x] `AGENTS.md` integration without replacing existing project instructions
- [x] TOML and integrity checks through `forgequorum doctor`
- [x] Unit tests and GitHub Actions configuration
- [x] English + Russian getting-started documentation

## v0.2.0 — shipped: safety, profiles and offline routing

- [x] Curated project profiles (`python`, `web`, `security`, `infra`, `full`)
- [x] `status` / `doctor --json` for CI-friendly diagnostics
- [x] Local Russian/English keyword-based task suggestions (`recommend`)
- [x] Manifest path allowlist and legacy manifest upgrade tests

## v0.2.x — remaining reliability & distribution

- [ ] Per-user installation (`~/.codex/agents` and `~/.agents/skills`) with strict conflict handling
- [ ] Transaction journal and recovery after forced interruption
- [ ] Release build checks and signed checksums
- [ ] Windows/macOS/Linux smoke test with a pinned Codex CLI version

## v0.3 — deeper agent orchestration

- [ ] Worktree-aware parallel implementers with explicit ownership
- [ ] Progress dashboard (active subagents, artifacts, failures, verified checks)
- [ ] Cost/context budget configuration and smart agent selection
- [ ] Persisted handoff summaries with credential/PII redaction
- [ ] Deterministic quality gates with explicit allow/deny policies

## v0.4 — optional GPT API engine

- [ ] Independent optional orchestration adapter using supported OpenAI APIs
- [ ] Typed task contracts and resumable execution
- [ ] Tool permissions, sandbox separation and audit events
- [ ] Automated evaluation suite for quality/cost/duration vs single-agent baseline

## Design principles

1. Prove benefits against a single agent; many agents are not a goal in themselves.
2. Never confuse model instructions with actual permission enforcement.
3. Preserve user files and make installation/uninstallation reversible.
4. Use documented, current Codex interfaces; avoid brittle patches.
5. Report genuine verification, not generated success claims.
