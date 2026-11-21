# ForgeQuorum

### One prompt. An entire engineering team.

**52 specialist roles · 39 reusable skills · 25 curated profiles · Native Codex integration**

ForgeQuorum is an independent, open-source, polyglot engineering toolkit for Codex: developer roles, reusable skills, safe project installation, deterministic routing and verifiable quality gates.

## Choose your installation method

**Native Codex plugin (skills only):** In a Codex client that supports plugin marketplaces, add the ForgeQuorum marketplace and enable the plugin:

```text
codex plugin marketplace add DizzyZ7/Forge-Quorum
```

Invoke `$route-task`, `$verification-loop`, `$test-driven-loop` or `$context-checkpoint`. Custom subagent roles are **not** installed by the plugin; use the CLI installation below. Live plugin installation has not been confirmed on every Codex client/version.

**Project CLI (agents and skills):**

```bash
python -m pip install --upgrade "git+https://github.com/DizzyZ7/Forge-Quorum.git"
fq inspect --target ./my-project
fq init --target ./my-project --profile auto
fq doctor --target ./my-project
```

Avoid installing the same skill through both methods. Hooks are opt-in and are never silently enabled. `fq verify` proposes commands without running them; `fq verify --run` explicitly executes project-defined code and is **not** a sandbox. See the [capability and limitations inventory](docs/CAPABILITIES.md) and [official Codex plugin documentation](https://developers.openai.com/plugins/build/plugins).

---

> **v0.4.0 is a configuration pack, not an autonomous agent runtime.** Actual subagent execution is delegated to Codex, subject to client support, sandbox permissions and available tools. Roles are instructions, not separate trained models.

[Русская документация](README.md) · [Language support](docs/LANGUAGE-SUPPORT.md) · [Architecture](docs/ARCHITECTURE.md) · [Roadmap](ROADMAP.md)

## Quick start

Python **3.11+ is only required to run the installer**; your target project may use any language.

```bash
python -m pip install --upgrade "git+https://github.com/DizzyZ7/Forge-Quorum.git"
fq inspect --target ../your-project
fq profiles
fq init --target ../your-project --profile auto --dry-run
fq init --target ../your-project --profile auto
fq doctor --target ../your-project
fq recommend "Implement a Kotlin Ktor API with tests" --target ../your-project --profile auto
```

Open `../your-project` in Codex and ask:

```text
$route-task Implement the requested feature using existing project conventions.
Select only necessary language-specific specialists, assign non-overlapping file
ownership, run the actual build/tests, report evidence and request approval
before publishing or deploying anything.
```

## Why this approach?

- **Native Codex assets:** `.codex/agents/<role>.toml` plus `.agents/skills/<skill>/SKILL.md`, with a marked block in `AGENTS.md`.
- **Language-specific specialists:** Node.js, JVM, Go, Rust, .NET, C++, mobile, desktop, game engines, data, ML and infrastructure.
- **Adaptive profiles:** 25 curated installation sets and a filename-based `auto` detector. The scanner does not read file contents or execute project commands.
- **Small teams, clear ownership:** `fq recommend` offers a bounded, deterministic suggestion (1–6 roles). Codex decides what actually runs.
- **Safe installation:** local SHA-256 manifest, preflight conflict detection, preservation of existing Codex config and user-modified managed files.

## CLI

```bash
fq list
fq profiles
fq inspect --target PATH --json
fq init --target PATH --profile go [--dry-run]
fq init --target PATH --profile mobile
fq init --target PATH --profile auto
fq init --target PATH --profile full
fq recommend "Build a Rust Tokio worker" --json
fq recommend "Add a backend endpoint" --target PATH --profile auto --json
fq status --target PATH --json
fq doctor --target PATH --json
fq uninstall --target PATH [--dry-run]
```

Stack detection is a **bounded heuristic**: it ignores dependency/build directories, skips symlinks, and looks at filename patterns and manifests. For a mixed monorepo, `backend` or `full` may be more appropriate than `auto`. Python is not required by generated applications or agent roles.

`recommend` uses deterministic offline rules; it neither invokes an LLM nor spawns subagents. The installed profile is recorded in the manifest. To change the profile, uninstall first and handle conflicts if local files were edited.

## Safety and limits

- Installer and scanner make no API requests, install no project dependencies, and do not execute target code.
- Existing `AGENTS.md` text and `.codex/config.toml` remain untouched outside owned sections.
- Read-only role guidance is **not** a security sandbox; Codex controls permissions.
- The manifest is local metadata, **not** a tamper-proof security boundary against an attacker who can edit it.
- Other languages' builds require their SDKs/runtimes and authorized tools. The CI matrix tests this Python CLI and generated files, not actual Codex execution on every stack.
- Publishing, infrastructure apply, production changes and destructive operations must follow the user's approvals.

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md), [ROADMAP.md](ROADMAP.md) and [CHANGELOG.md](CHANGELOG.md). We welcome focused roles, original workflows, portable examples and reproducible regression tests.

If ForgeQuorum helps, consider starring ⭐ the repository.

MIT License. Copyright © 2026 Dimash Janibekov. Independent community project; not affiliated with OpenAI.
