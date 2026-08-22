# ADR 0007: Isolated-clone shared package pins

- Status: Proposed
- Date: 2026-08-01
- Supersedes: ADR 0002 for application installation and build dependencies

## Context

Federation application repositories consumed shared Python packages through editable paths such as `-e ../thehub-pr/packages/prii_desktop`. Several desktop setup scripts compensated by cloning TheHub beside the application automatically. This made repository installation depend on a particular parent-directory layout, introduced implicit network and Git operations, and prevented clean isolated-checkout validation.

TheHub's local federation launcher separately scans sibling repositories to discover and launch installed applications. That is an operator convenience and is not an application package dependency.

## Decision

1. Every federation application must install, test, build, and package from an isolated checkout.
2. Shared packages are referenced by package name and an immutable source revision. Initial consumers pin the package subdirectory at TheHub commit `f2b81769924689b4d959554928810b1d7b7ef3d6`.
3. Desktop setup must not clone or require a sibling repository.
4. Local editable overrides may be supported only through an explicit developer action or configuration; they are never the default requirement.
5. TheHub may continue to discover sibling repositories for its optional local launcher. Missing siblings must be reported as unavailable applications and must not block TheHub startup.
6. Dependency upgrades require an explicit pin change and normal repository CI.

## Consequences

- Standalone clones become reproducible with respect to shared source identity.
- The declared installation still requires network access when the pinned Git dependency is not cached; that access is explicit in the requirement rather than hidden in setup code.
- A future dedicated package registry or shared-package repository may replace the pinned TheHub subdirectory source without changing the isolated-clone contract.
- Federation templates must emit pinned package references and must not regenerate sibling-path dependencies.

## Required validation

- No executable requirement references `../thehub-pr`.
- No setup path invokes `git clone` to manufacture a sibling checkout.
- Each affected repository passes tests, frontend build, desktop packaging, and GUI reachability from a checkout whose parent contains no federation siblings.
- TheHub launcher tests preserve graceful `present=false` behavior for absent applications.
