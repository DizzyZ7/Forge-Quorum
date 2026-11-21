---
name: automation-hardening
description: Make background jobs, bots and webhook pipelines reliable and resource-aware.
---

# automation-hardening

## Trigger
For Telegram bots, scheduled jobs, Redis queues, callbacks and third-party integrations.

## Procedure
1. Define unique work identity, durable state and concurrency limits.
2. Use idempotency keys and bounded retries with exponential backoff and jitter.
3. Document queue overflow, dead-letter and cancellation behavior.
4. Avoid duplicate downloads, double billing and unbounded cache growth.
5. Protect secrets and validate callbacks before executing actions.
6. Test duplicate delivery, timeouts, outages and recovery.

## Delegation policy
Ask integration-engineer for delivery semantics and python-backend for concrete implementation.

## Done when
Failure-mode matrix, implementation, resource budget and regression tests.
