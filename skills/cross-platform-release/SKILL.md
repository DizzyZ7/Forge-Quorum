---
name: cross-platform-release
description: Ship a multi-platform release with signed artifacts and compatibility checks.
---

# cross-platform-release

## Trigger
For multi-OS desktop/mobile packages and runtime compatibility.

## Procedure
1. Identify exact target OS, architectures and supported versions.
2. Verify deterministic builds, versioning, signatures and supply chain.
3. Test clean install, upgrade and uninstall with data preservation.
4. Prepare release notes and rollback/stop criteria.
5. Request explicit approval before publishing or distribution.

## Delegation policy
Use release-manager, desktop-engineer or mobile-qa.

## Done when
Reproducible release matrix and explicit unverified platform gaps.
