---
name: security-gate
description: Threat-model and review security-sensitive changes before release.
---

# security-gate

## Trigger
For login, access controls, secrets, uploads, webhooks, agents or external tool access.

## Procedure
1. List trusted and untrusted inputs, actors, assets and security boundaries.
2. Confirm authorization on the server side, not only in the UI.
3. Review injection, SSRF, path traversal, deserialization and unsafe tool execution.
4. Examine secret handling and dependency risks without printing credentials.
5. Describe plausible abuse paths and missing mitigations.
6. Test rejected/invalid inputs and least privilege where permitted.
7. Provide release-blocking findings separately from defense-in-depth suggestions.

## Delegation policy
Delegate to security-auditor or threat-modeler; never run offensive tests against unauthorized systems.

## Done when
Severity-scored findings with redacted proof, mitigation and verification plan.
