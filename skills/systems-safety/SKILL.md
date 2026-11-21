---
name: systems-safety
description: Review native, OS and firmware changes against failure and memory safety.
---

# systems-safety

## Trigger
For C/C++, embedded, kernel-adjacent, drivers or critical interfaces.

## Procedure
1. Identify ownership/privilege boundaries and supported hardware.
2. Audit unsafe memory, threading, interrupts and system call errors.
3. Separate simulator checks from hardware validation.
4. Run sanitizers or static analysis when available and permitted.
5. Document rollback/recovery and untested hardware.

## Delegation policy
Use cpp-engineer, embedded-engineer or systems-engineer with reviewer.

## Done when
Safety review with reproductions, tests and critical blockers.
