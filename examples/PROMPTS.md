# Practical Codex prompts

## 1. Full-stack feature

```text
$build-feature Implement user profile editing with FastAPI and a React form.
Preserve API compatibility. Ask repo-explorer to map the current implementation;
only delegate independent backend/frontend files. Include accessible empty/loading/error
states, validation, tests and a short final report with executed test commands.
```

## 2. Independent review

```text
$deep-review Review the changes against main for concurrency, authorization,
backward compatibility, and missing regression tests. Use independent read-only
review roles when appropriate. Report findings with file/line evidence.
```

## 3. Telegram bot / Redis

```text
$automation-hardening Audit the queue worker: the same media URL can arrive
repeatedly, and redis memory is limited. Design dedupe keys, bounded jobs,
resource limits, cancellation and correct crash recovery. Implement and test
repeated delivery, failed downloads and worker restart.
```

## 4. Security audit

```text
$security-gate Review this project's authorization, public endpoints and webhook
signatures. Never print secrets. Do not make external offensive requests. Return
prioritized issues, safe reproductions and recommended tests.
```

## 5. Production migration preparation (no execution)

```text
$data-migration Prepare an expand-contract PostgreSQL migration for renaming
account_id to customer_id without downtime. Provide a backfill, read/write
compatibility window, verification queries, abort conditions and rollback.
Do not execute production DDL.
```

## CLI task recommendation (v0.2.0)

```bash
fq recommend "Исправь повторную доставку событий в Redis" --profile python --json
fq recommend "Build a responsive React dashboard" --profile web
fq recommend "Audit API authorization" --profile security --max-agents 2
```

These are offline heuristic suggestions. Paste the generated `$skill` prompt into a
Codex session to actually delegate work.
