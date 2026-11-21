---
name: deep-review
description: Run an evidence-first independent review of a diff, pull request or module.
---

# deep-review

## Trigger
Before merging nontrivial code or when user requests senior-level review.

## Procedure
1. Define the base revision and actual changes; do not assume every file in the repository changed.
2. Trace each affected external interface and permission boundary.
3. Check failures, concurrency, contracts, compatibility, data integrity and security.
4. Check tests for real coverage and look for missing counterexamples.
5. Separate verified findings from suspicions; cite affected file and line.
6. Prioritize critical correctness issues before styling feedback.
7. If no bugs are found, say so and mention residual risks.

## Delegation policy
Use reviewer, security-auditor and test-engineer as independent read-only reviewers when changes merit parallel review.

## Done when
Concrete findings ordered by severity; each has evidence and how to reproduce or fix.
