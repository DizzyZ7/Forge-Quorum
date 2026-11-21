# ForgeQuorum

**One prompt. An entire engineering team.**

[![Tests](https://github.com/DizzyZ7/Forge-Quorum/actions/workflows/tests.yml/badge.svg)](https://github.com/DizzyZ7/Forge-Quorum/actions/workflows/tests.yml)

An original Codex-native multi-agent engineering pack: 20 role-specific subagents, 14 reusable skills, and a safe, standard-library-based installer.

> v0.1.0 is an installable configuration pack, not an independent API orchestration service. Codex itself runs native subagents. The presence of an agent definition does not guarantee that Codex will spawn that agent for every task.

## Install

```bash
python -m pip install "git+https://github.com/DizzyZ7/Forge-Quorum.git"
forgequorum init --target ../your-project
forgequorum doctor --target ../your-project
```

The short CLI alias `fq` also works. Or install from a local checkout:

Requires Python 3.11+ and Codex for actual agent execution.

```bash
python -m pip install -e .
forgequorum init --target ../your-project --dry-run
forgequorum init --target ../your-project
forgequorum doctor --target ../your-project
```

Then open your project with Codex:

```text
$route-task Implement a safe password reset flow with tests and independent security review. Delegate only independent work and report actual test results.
```

## Design

- Native `.codex/agents/<role>.toml` custom agents and `.agents/skills/<skill>/SKILL.md` workflows.
- Task routing emphasizes *minimal*, meaningful delegation rather than agent count.
- Separate read-only analysis and verification roles from write-capable implementers. This is a prompt-level convention, **not** a sandbox.
- No API keys, cloud services, hooks, secret exfiltration or external network calls required by the installer.
- Existing `AGENTS.md` is preserved; existing `.codex/config.toml` is never overwritten.
- SHA-256 manifest guards against accidental loss of locally modified managed files on update/uninstall.

## CLI

```bash
forgequorum list
forgequorum init --target PATH [--dry-run]
forgequorum doctor --target PATH
forgequorum uninstall --target PATH [--dry-run]
```

For the roles, skills, security notes, architecture, roadmap, and actual limitations see the [Russian README](README.md) and [ROADMAP](ROADMAP.md).

## Test

```bash
python -m unittest discover -s tests -v
```

Independent community project; not affiliated with OpenAI.

If you find ForgeQuorum useful, consider ⭐ [starring this repository](https://github.com/DizzyZ7/Forge-Quorum). Issues and contributions are welcome.

MIT License. Copyright (c) 2026 Dimash Janibekov.
