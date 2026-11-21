# Changelog

## 0.2.0 — 2026-11-21

### Added

- Curated project installation profiles: `python`, `web`, `security`, `infra`, `full`.
- `forgequorum profiles`, `status`, and offline bilingual `recommend` CLI commands.
- JSON diagnostics for `doctor` and `status`, suitable for CI/automation.
- Explicit profile metadata in manifest format 2, with compatibility for v0.1.0 manifests.
- Ten regression tests for profiles, upgrade, task routing, and manifest tampering.

### Security / compatibility

- Strict allowlist for paths in editable manifests: a forged manifest can no longer enlist arbitrary project files for removal.
- Changes to a previously installed profile require explicit uninstall first; no silent destructive profile migration.
- The Python installer remains dependency-free at runtime, and agent execution still belongs to Codex.

## 0.1.0 — 2026-11-21

### Added

- Original Codex-native library of 20 specialized subagent roles.
- 14 procedural skills for feature delivery, testing, security, reliability and release readiness.
- Project-scoped `forgequorum init`, `doctor`, `list` and `uninstall` commands.
- Idempotent installer with dry-run, conflict preflight and SHA-256 manifest.
- Preservation of existing project `AGENTS.md` and Codex configuration.
- Unit test suite, cross-platform GitHub Actions workflow, Russian and English docs.

### Known limitations

- Runtime agent execution is handled by Codex, not by the Python CLI.
- Installing into the current user's global Codex config is not yet available.
- Existing Codex config must be manually merged with the generated example.
- No live Codex end-to-end run was performed in the build environment.
