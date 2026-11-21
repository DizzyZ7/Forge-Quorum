---
name: kubernetes-operations
description: Harden Kubernetes deployment manifests and rollout readiness.
---

# kubernetes-operations

## Trigger
For Kubernetes, Helm, Kustomize or GitOps changes.

## Procedure
1. Map namespaces, service accounts and cluster contexts.
2. Verify limits, probes, disruption budgets, network policies and secrets.
3. Run static or dry-run checks without changing the cluster.
4. Describe rollback, monitoring and workload behavior.
5. Apply only with explicit approval and authorized access.

## Delegation policy
Use kubernetes-engineer and sre-engineer.

## Done when
Validated manifests and observable rollout plan.
