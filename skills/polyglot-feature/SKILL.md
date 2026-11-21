---
name: polyglot-feature
description: Deliver features spanning different languages/services while preserving contracts.
---

# polyglot-feature

## Trigger
When a feature touches more than one runtime, SDK, service or language.

## Procedure
1. Inventory languages, versioned APIs, dependencies and current test commands.
2. Define explicit contracts and compatibility rules across components.
3. Partition work by ownership so independent agents do not edit shared files.
4. Integrate sequentially at shared boundaries and run actual cross-stack tests.
5. Report untested runtimes and rollout needs.

## Delegation policy
Use the smallest number of stack-native implementers plus one reviewer.

## Done when
Compatible end-to-end change with observable test evidence.
