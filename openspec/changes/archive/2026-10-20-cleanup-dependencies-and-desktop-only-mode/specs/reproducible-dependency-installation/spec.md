# Spec Delta

## Purpose

Defines repeatable dependency installation and build inputs for the supported desktop development and release environments.

## ADDED Requirements

### Requirement: Reviewed dependency versions
The project SHALL record explicit compatible versions for all direct Python, Rust, and frontend dependencies and SHALL exclude unneeded direct dependencies.

#### Scenario: Dependency review
- **WHEN** a maintainer reviews the manifests
- **THEN** each direct dependency has a verified consumer or required build role and no frontend dependency uses `latest`

### Requirement: Repeatable local installation
The project SHALL provide documented lock-based installation for supported Python, npm, and Cargo build environments, including transitive dependencies where their package manager supports locking.

#### Scenario: Repeated setup
- **WHEN** two maintainers install from the same revision on the same supported platform and interpreter/toolchain versions
- **THEN** they resolve the same dependency versions

#### Scenario: Lock and manifest disagreement
- **WHEN** a manifest and its lock input disagree
- **THEN** the documented reproducible-install command fails rather than silently selecting newer versions

### Requirement: Package-manager compatibility
The project SHALL document how pinned local builds coexist with distribution-managed Python dependencies in the Linux package recipe.

#### Scenario: AUR installation
- **WHEN** the AUR package is installed through the distribution package manager
- **THEN** it uses the declared system Python packages and does not require pip to overwrite them

### Requirement: Measured build-size changes
The project SHALL record comparable before and after build sizes. Any runtime performance optimization SHALL be preceded by measurement of the affected execution path.

#### Scenario: Cleanup review
- **WHEN** dependency or bundle changes are proposed for completion
- **THEN** the review shows before and after sizes under the same build procedure

#### Scenario: Runtime optimization proposal
- **WHEN** a concrete runtime slowdown is identified
- **THEN** its execution path is measured before an optimization is proposed
