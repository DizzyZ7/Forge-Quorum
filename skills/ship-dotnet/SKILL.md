---
name: ship-dotnet
description: Implement .NET features and check dependency lifetimes and migrations.
---

# ship-dotnet

## Trigger
For C# APIs, workers, desktop apps and libraries.

## Procedure
1. Inspect target frameworks, NuGet and existing solution structure.
2. Review DI, tasks, cancellation and validation.
3. Implement tests and update contracts.
4. Run dotnet build/test when available.
5. Document target runtime and deployment requirements.

## Delegation policy
Use dotnet-engineer and qa-automation; add database-engineer if necessary.

## Done when
Buildable .NET change with checks.
