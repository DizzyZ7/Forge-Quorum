---
name: context-checkpoint
description: Create a compact, privacy-conscious project checkpoint between Codex sessions.
---

# context-checkpoint

## Trigger
Use when pausing a complex task or preparing a clean handoff to a new agent or session.

## Procedure
1. Summarize agreed goal, decisions, changed files, blockers and next actions in your own words.
2. Use fq context for a filename-only overview; do not copy secrets or full logs.
3. Use fq checkpoint --note with a short non-sensitive note if local persistence is wanted.
4. Re-check actual repository state on resume; a checkpoint is not an authoritative transcript.
5. Keep checkpoints local and excluded from version control unless explicitly reviewed.

## Delegation policy
Use planner or repo-explorer; do not automatically record chat transcripts.

## Done when
Compact handoff with open decisions, tests actually run and next smallest action.
