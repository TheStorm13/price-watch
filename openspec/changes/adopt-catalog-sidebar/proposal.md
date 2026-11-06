# Proposal

## Why

The approved sidebar demo must become the actual desktop interface. The current production header still uses the superseded filters and group semantics.

## What Changes

- Replace the header with the approved permanent 260 px sidebar and compact catalog UI documented in `docs/guide/SIDEBAR_IMPLEMENTATION_CHECKLIST.md`.
- Move global add, refresh, create-group, import/export, Chrome and real background settings into the shell; keep one collection panel at the sidebar bottom.
- **BREAKING**: replace single marketplace/tag filters and column/update sorting with multiple choices, stock checkbox and the three agreed sorts. Remove demo gates and old UI branches.
- Filter individual group members, project their sorted representative and count individual products.
- Keep explicit contextual return from details, with an inert Price watch brand.

## Capabilities

### New Capabilities
- `catalog-sidebar`: Permanent sidebar, filter controls and catalog counts.

### Modified Capabilities
- `group-card-metrics`: Per-member filtering and representative selection under current sort.

## Impact

Frontend shell, catalog model/rendering, settings trigger, mock E2E fixtures/tests and UI documentation. Keep existing Tauri commands, API contracts, collection lifecycle and persistence. No database migration, dependency, worker, CLI or JSON-mode changes. Acceptance: all approved demo behaviors work on the normal route and production build, real command wiring survives, old UI/demo paths are removed, relevant unit/E2E/build checks pass.
