# Sidebar layout demos

## Plan and authorization

2026-11-05: user approved implementing a UI demo with two variants after reviewing the sidebar proposal. Keep one catalog. In both variants global actions move into a permanent sidebar; collection status appears across its width at the very bottom. Variant 1 retains catalog search/filters/sort/group creation; variant 2 moves these into the sidebar. Use existing UI and isolated mock data.

User message: «Хорошо, реализуй демо версию как это будет на ui. А также вторую версию где ты перенесешь фильтры, создание групп, сортировку в панель».

## State

Implementation and verification finished; preparing the implementation commit for user evaluation. OpenSpec: `demo-sidebar-layouts`. Production layout selection and explicit acceptance are pending. Do not sync/archive yet.

## Verification plan

Type check, frontend unit suite, relevant catalog/layout E2E plus new variant/collection flows; production frontend build. Browser plugin is not available, so rendered validation uses Playwright. Inspect 1440×900 and minimum supported 1024×768; mobile is outside the desktop product's minimum width.

## Entry

Run `npm --prefix frontend run dev:demo`. Open `/cards?sidebar=1` or `/cards?sidebar=2` on its reported localhost address. Data and desktop-only dialogs are simulated. The mock collection pauses for verification; use «Проверка пройдена» to continue.

## Next action

Commit the reviewed task files, present the two running demo links and wait for user evaluation. Do not archive until accepted.

## Verification results

- `npm --prefix frontend run lint`: passed (RTK output was unusable; verified using `rtk bypass npm run lint` from frontend).
- `npm --prefix frontend test`: 110 tests / 21 files passed, including a rerun after the shared catalog changes.
- `npm --prefix frontend run test:e2e -- sidebar-demo.spec.ts app.spec.ts layout.spec.ts usability.spec.ts`: 50 passed. Covers preserved search/sort/grid across switching, group creation, reset/reload retaining variant, global actions in details, collection challenge/continuation/completion/dismissal and bottom anchoring at 1440×900 / 1024×768.
- `npm --prefix frontend run desktop:build`: passed; release binary built. Final `build:desktop` rerun also passed; production build contains no SidebarDemo chunk.
- `openspec validate demo-sidebar-layouts --strict` and `git diff --check`: passed.
- Playwright rendered review: both variants, narrow idle layout and verification panel; no page or console errors in the inspected demo flow. At 1024 px document width is 1024 px; panel width 259 px inside the 260 px sidebar and panel bottom is exactly 768 px. Middle section scrolls independently. Inspected control placement, active variant, spacing, labels, table overflow and progress/action visibility. Screenshots and temporary inspection scripts stay in `/tmp`, outside committed source.
- Existing E2E logs include React Router's `No HydrateFallback element provided` warning on lazy detail routes; the checks passed. No router hydration change is part of this demo.
- Browser plugin absent; IAB opening was also unavailable (`Browser is not available: iab`). Preview remains available through localhost links.

## Review and boundaries

Repowise CLI index refreshed with `repowise update --working-tree`; the MCP risk response still reports its older index metadata. Its live-diff findings concern component cyclomatic complexity and unsupported CSS analysis; reviewed the actual diff, scoped CSS and portal ownership directly. It also reported stale dependency paths despite no package-lock/dependency changes in this task, so that test recommendation is not used as current evidence.

Changed surfaces: opt-in shell activation, preview shell/slot module, catalog control placement, optional labelled import/export trigger, scoped global CSS, demo npm script, four E2E cases and OpenSpec artifacts. Global add/import/collection actions reuse existing dialogs and commands; filter/group portals preserve CardsPage ownership. Preview settings are local state; Chrome and exit behavior are explanatory simulation. No native runtime, API, worker, CLI, JSON-mode or persisted data changes; live service/database behavior was not tested.

The initial new E2E run passed three cases and found an ambiguous close-button locator in the fourth. The dialog action was renamed to «Готово» and all four subsequently passed in the 50-case run. A visual review also caught and fixed the import trigger's inherited flex order.
