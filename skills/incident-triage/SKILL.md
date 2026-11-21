---
name: incident-triage
description: Structure a production incident investigation without unsafe automatic changes.
---

# incident-triage

## Trigger
For outages, error spikes, degraded services and urgent triage.

## Procedure
1. Define symptoms, impact, time window and current customer harm.
2. Create a timeline from observed metrics/logs; redact secrets and PII.
3. Prioritize safe mitigation, isolation and rollback options.
4. Compare candidate causes with falsifiable observations.
5. Obtain approval before production rollbacks, access changes or destructive actions.
6. Track recovery signals and confirm user-visible functionality.
7. Prepare short post-incident follow-ups and preventive checks.

## Delegation policy
Use debugger, devops-engineer and observability-engineer on independent evidence sources.

## Done when
Incident summary with verified facts, mitigation options, timeline and follow-ups.
