---
name: infrastructure-plan
description: Review an infrastructure change safely before any apply.
---

# infrastructure-plan

## Trigger
For Terraform, OpenTofu, Pulumi or cloud resource changes.

## Procedure
1. Identify impacted environments, account, state and IAM boundaries.
2. Run validation and plan/diff only in authorized environment.
3. Inspect blast radius, secrets, cost and rollback.
4. Require explicit approval before apply, destroy or production mutation.
5. Collect post-change monitoring criteria.

## Delegation policy
Use terraform-engineer, cloud-architect and security-auditor.

## Done when
Reviewable proposed plan and go/no-go decision, no unapproved changes.
