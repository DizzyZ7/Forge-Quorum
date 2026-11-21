---
name: build-mobile
description: Deliver a mobile feature with permissions, lifecycle and accessibility checks.
---

# build-mobile

## Trigger
For Android, iOS, SwiftUI, Jetpack Compose and Flutter.

## Procedure
1. Identify platform/SDK versions, device constraints and existing navigation/state architecture.
2. Design permission and offline/failure states before coding.
3. Separate shared and native component ownership.
4. Run available platform builds and tests; mark missing hardware checks.
5. Verify upgrades, backgrounding, accessibility and release impact.

## Delegation policy
Use android-engineer, swift-engineer or flutter-engineer, plus mobile-qa.

## Done when
Mobile implementation with device/OS test matrix and limitations.
