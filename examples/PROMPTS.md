# Multi-stack prompts

Use these inside a Codex session **after** installing a suitable ForgeQuorum profile.

## TypeScript + Go backend

```text
$polyglot-feature Implement a TypeScript frontend consuming a Go API.
Inspect actual package versions, define the API contract, assign separate frontend
and backend file ownership, test both sides and report unavailable checks.
```

## Android / Flutter

```text
$build-mobile Add offline task editing to this Flutter application.
Consider lifecycle, state restoration, permissions, accessibility and upgrades.
Use device-specific verification only when a simulator or device is available.
```

## Rust worker

```text
$ship-rust-crate Create a cancellable worker with bounded concurrency.
Use existing Cargo conventions; check error behavior, race-prone transitions
and shutdown paths. Provide tests and real cargo results.
```

## JVM business service

```text
$ship-jvm-service Add an idempotent Spring Boot endpoint with transaction
boundaries, authentication checks and negative tests. Keep backward compatibility.
```

## Security-first infrastructure plan

```text
$infrastructure-plan Review this Terraform change without applying anything.
List resources and IAM deltas, blast radius, cost and rollback criteria.
```

## ML / RAG

```text
$ml-lifecycle Implement a retrieval pipeline with a reproducible evaluation set,
real baseline metrics and leakage checks. Don't invent model quality or costs.
```
