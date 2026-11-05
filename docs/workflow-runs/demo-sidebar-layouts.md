# Sidebar layout demos

## Plan and authorization

2026-11-05: user approved implementing a UI demo with two variants after reviewing the sidebar proposal. Keep one catalog. In both variants global actions move into a permanent sidebar; collection status appears across its width at the very bottom. Variant 1 retains catalog search/filters/sort/group creation; variant 2 moves these into the sidebar. Use existing UI and isolated mock data.

User message: «Хорошо, реализуй демо версию как это будет на ui. А также вторую версию где ты перенесешь фильтры, создание групп, сортировку в панель».

## State

First iteration committed as `1d1663e`. The user selected layout 2 and authorized a revised demo. Revision implementation and checks passed; preparing the checked revision commit for evaluation. OpenSpec: `demo-sidebar-layouts`. Explicit acceptance of the revision and production adoption are pending. Do not sync/archive yet.

## Approved revision

2026-11-05: user requested removal of the catalog title/subtitle; name/article search above results; multi-select marketplaces and tags; one «Только в наличии» checkbox; sorting first among sidebar filters with deal-first default and ascending/descending price only; deal labels «Все предложения», «Выгодные», «Невыгодные». Tags default to all and match OR. User explicitly confirmed: «Наличие это чекбокс. один чекбокс “Только в наличии” … Теги по умолчанию все. Товар тожен содержать хотя бы один. Теперь сделай новое демо».

Replace the two-layout comparison with the selected refined preview, retaining one catalog and bottom status. Keep the changes demo-only. Use compact multi-select checkbox popovers to preserve vertical space. Add two mock marketplace samples and meaningful tags through existing mock import/update operations; no persisted data or live services are involved.

## Verification plan

Type check, frontend unit suite, relevant catalog/layout E2E plus new variant/collection flows; production frontend build. Browser plugin is not available, so rendered validation uses Playwright. Inspect 1440×900 and minimum supported 1024×768; mobile is outside the desktop product's minimum width.

## Entry

Run `npm --prefix frontend run dev:demo`. Open `http://127.0.0.1:5176/cards?sidebar=2`. Data and desktop-only dialogs are simulated. The mock collection pauses for verification; use «Проверка пройдена» to continue. Marketplace/tag popovers default to all; clear the general checkbox before selecting a subset. An explicitly empty subset matches nothing.

## Next action

Commit the reviewed revision files and present the revised demo for user evaluation. Do not archive until accepted.

## First iteration verification

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

## Revision verification

- Type check: `rtk bypass npm run lint` passed.
- Unit suite: 113 tests / 22 files passed, including OR tags, all/empty selections, untagged defaults, decimal price sorting across deal priority, null prices, article-vs-internal-ID search and unknown availability.
- New preview E2E: six scenarios passed. Covers combined marketplace/tag filters, keyboard focus after popovers, reload, search by article, detail return, group creation, all three sorts/deal filters and collection continuation/completion at 1440×900 and 1024×768.
- Native `npm --prefix frontend run desktop:build` passed; final `build:desktop` passed after scoped column-width adjustments.
- Playwright screenshots in `/tmp/sidebar-revised*.png` inspected using `view_image`: full layout, multi-select popup, narrow layout and verification panel. No page/console errors in the inspected demo flow, correct page title/URL, meaningful results and no framework overlay. At 1024 px the document stays 1024 px wide and the progress panel is 259 px wide, ending at y=768. Scoped column widths keep marketplace labels separate from prices and current prices visible before the sticky availability column.
- Repowise live-diff review reports pre-existing large React functions becoming slightly more complex plus conditions in preview sorting/bootstrap; checked the actual branches, mock-only fixture guard and shared renderer default. CSS is unsupported by that analyzer and was reviewed in the browser. MCP metadata/test recommendations still reflect its stale index despite a CLI refresh; no package-lock/dependency changes occurred.
- Live API/worker/database/native WebView behavior is outside this mock-only revision. No migrations or changes to desktop production controls.

Broader regression command `npm --prefix frontend run test:e2e -- sidebar-demo.spec.ts app.spec.ts layout.spec.ts usability.spec.ts`: 52 passed (3.4 minutes). Existing lazy-route HydrateFallback warnings remain as in the first iteration; no new runtime errors were found. `openspec validate demo-sidebar-layouts --strict` and `git diff --check` passed. Review the staged diff and commit before presenting the revision for evaluation.
