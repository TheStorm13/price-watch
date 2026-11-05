# Proposal

## Why

Refine the selected second sidebar layout on isolated sample data before choosing the production UI. Keep one catalog, a search field above results and collection status at the very bottom of the sidebar.

## What Changes

- Provide one opt-in, mock-data-only demo of the selected sidebar layout; remove the superseded comparison switcher.
- Remove the catalog title/subtitle and place name/article search above results.
- Keep actions, group creation and filters in the sidebar. Sorting is the first filter, with deal-first default and pure ascending/descending price choices.
- Allow multiple marketplaces and OR-matched tags, all selected by default; provide one availability checkbox and clear deal-filter labels.
- Anchor the existing collection panel to the bottom of the sidebar, with independent scrolling above it.
- Keep catalog interactions functional and simulate desktop-only Chrome/settings actions explicitly.

## Capabilities

### New Capabilities

- `sidebar-layout-preview`: isolated interactive preview of the selected catalog sidebar layout.

### Modified Capabilities

None. The production desktop layout and contracts remain unchanged during evaluation.

## Impact

Frontend shell, catalog controls/results, demo-only filtering and fixture, scoped CSS, unit/E2E coverage. No new dependencies, API changes, database migration, CLI/worker execution changes or access to user data. Acceptance: requested controls work together and survive reload/return from details; price order includes all matching products without deal-priority overrides; null prices are last; group/add dialogs work; bottom progress remains accessible at 1440 and 1024 px; desktop retains its existing layout.
