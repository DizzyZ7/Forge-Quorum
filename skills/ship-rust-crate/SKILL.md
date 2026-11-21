---
name: ship-rust-crate
description: Implement Rust features with sound ownership and unsafe-boundary review.
---

# ship-rust-crate

## Trigger
For Rust services, libraries and native components.

## Procedure
1. Inspect Cargo workspace features, MSRV and CI.
2. Review ownership, error paths, async cancellation and unsafe uses.
3. Implement stable API and unit/doc tests.
4. Run cargo fmt, clippy and relevant tests if installed.
5. Document FFI/platform behavior and performance constraints.

## Delegation policy
Use rust-engineer and reviewer.

## Done when
Correct Rust change with reproducible checks and compatibility notes.
