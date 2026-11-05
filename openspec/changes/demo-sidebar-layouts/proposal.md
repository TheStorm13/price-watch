# Proposal

## Why

Compare two permanent sidebar layouts in the existing catalog before choosing a production UI. Keep one catalog and make the collection panel appear at the very bottom of the sidebar.

## What Changes

- Add an opt-in, mock-data-only demo with two switchable layouts.
- Move global actions into the sidebar in both layouts; move search, filters, sorting and group creation there only in layout 2.
- Anchor the existing collection panel to the bottom of the sidebar, with independent scrolling above it.
- Keep catalog interactions functional and simulate desktop-only Chrome/settings actions explicitly.

## Capabilities

### New Capabilities

- `sidebar-layout-preview`: isolated interactive comparison of two catalog sidebar layouts.

### Modified Capabilities

None. The production desktop layout and contracts remain unchanged during evaluation.

## Impact

Frontend shell, catalog control placement, import/export trigger label, scoped CSS, demo launch script and E2E coverage. No new dependencies, API changes, database migration, CLI/worker/collection execution changes or access to user data. Acceptance: both layouts preserve a single catalog and filters across switching; group/add dialogs work; progress is sidebar-wide and bottom-anchored at 1440 and 1024 px; the usual desktop build retains its existing layout.
