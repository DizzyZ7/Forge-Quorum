---
name: ml-lifecycle
description: Deliver ML/RAG features with meaningful evaluation and rollback.
---

# ml-lifecycle

## Trigger
For traditional ML, LLM applications, RAG and model serving.

## Procedure
1. Define task metrics and holdout evaluation before model changes.
2. Identify leakage, unsafe training data, licensing and privacy constraints.
3. Implement versioned prompts/models/data and baseline tests.
4. Evaluate representative adverse cases, latency and cost.
5. Document drift monitoring and a rollback strategy.

## Delegation policy
Use ml-engineer and mlops-engineer; add security-auditor when exposing tools.

## Done when
Reproducible eval report and bounded serving plan.
