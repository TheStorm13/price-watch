# Proposal

## Why

The deal-count banner interrupts the catalog and carries its own durable queue and retry machinery. Screenshot artifacts and manual baseline review add maintenance without replacing behavioral assertions; historical migrations need evidence-based review rather than deletion by age.

## What Changes

- Remove the deal-count banner, notification queue, storage-version adapters and notification-only tests. Keep deal selection/filtering and refresh the catalog after every terminal collection run.
- Remove the tinted separator in the collection panel footer locally, preserving scrolling and progress/actions visibility.
- Remove manual screenshot production and baseline-review requirements from the test workflow. Replace unique useful visual scenarios with automatic behavior/layout assertions; remove redundant visual scenarios, baselines, config and script when their useful coverage is retained.
- Audit migration chains and suspicious obsolete paths. Preserve the continuous 0001–0018 upgrade chain and data-preservation checks; consolidate only proven duplicate test setup/scenarios. Record retained items and reasons.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deal-notifications`: retire notification requirements and require collection completion to refresh catalog data without a deal-count notification.
- `desktop-ui-layout`: remove the deal notification layout requirement.

## Impact

Frontend collection provider, shell, collection panel, notification and layout tests, E2E screenshot suite/config/scripts and testing guide. No new dependencies, API changes or database migration. Existing notification storage becomes inert; no compatibility reader or cleanup migration is needed. CLI, worker, numeric JSON mode and user data retain their contracts.

Acceptance: no deal-count banner/queue/retry requests; completed, completed-with-errors and failed runs still invalidate catalog data; footer has no tinted strip; tests require no manual PNG acceptance and preserve unique useful behavior/layout coverage. Run relevant Python tests, frontend unit/type/E2E checks and desktop build. PostgreSQL checks use only a disposable TEST_DATABASE_URL; report unavailable checks.
