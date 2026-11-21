# Changelog

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
