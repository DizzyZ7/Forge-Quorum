# Contributing

This project contains original role definitions and reusable Codex skills. Contributions should improve observable engineering outcomes, not maximize agent or skill count.

## Before opening a PR

1. Explain the concrete scenario and why a new role or workflow is necessary.
2. Prefer refining a current role before adding an overlapping one.
3. Keep explicit security, evidence and collaboration constraints.
4. Add tests for every installer change, including upgrades and conflicts.
5. Run `python -m unittest discover -s tests -v` and record the result.
6. Document API/UX changes in both README files where relevant.

Do not include API keys, personally identifiable data, private repository contents, or unlicensed copied agent definitions in issues or pull requests.

## Role definition requirements

Each agent needs a clear name, mission, nonoverlapping focus and verifiable output artifact. Read-only roles must explicitly avoid file writes; remember that this is advisory, not a security sandbox.

## Skill definition requirements

Each skill needs a trigger, ordered procedure, delegation policy and done criteria. Avoid unverifiable promises or instructions to autonomously deploy, publish or bypass permissions.

## Contributing skill changes (v0.4+)

Edit the source-of-truth workflow specs in `src/forgequorum/registry.py`,
`src/forgequorum/polyglot.py`, or `src/forgequorum/extra_workflows.py`.
Generate Codex plugin exports with `python tools/sync_skills.py`, then run
`python tools/sync_skills.py --check` and `python -m unittest discover -s tests -v`.
Generated root `skills/` content must not drift from the Python catalog.

Add routing regression cases to `evals/routing.jsonl` whenever task routing changes,
then run `python tools/evaluate_routing.py`. Do not copy third-party agent
instructions or imply live Codex integration without an integration test.
