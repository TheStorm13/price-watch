# Sidebar layout demos

## Plan and authorization

2026-11-05: user approved implementing a UI demo with two variants after reviewing the sidebar proposal. Keep one catalog. In both variants global actions move into a permanent sidebar; collection status appears across its width at the very bottom. Variant 1 retains catalog search/filters/sort/group creation; variant 2 moves these into the sidebar. Use existing UI and isolated mock data.

User message: «Хорошо, реализуй демо версию как это будет на ui. А также вторую версию где ты перенесешь фильтры, создание групп, сортировку в панель».

## State

First iteration committed as `1d1663e`; selected-layout refinement as `58324da`; heading/selection revision as `9fe3ade`; popup-width revision as `77ffa59`; count/compact-button revision as `ab493df`. User requested left-side card creation. This correction is implemented and verified; preparing its commit for evaluation. OpenSpec: `demo-sidebar-layouts`. Explicit acceptance of the current revision and production adoption are pending. Do not sync/archive yet.

## Approved revision

2026-11-05: user requested removal of the catalog title/subtitle; name/article search above results; multi-select marketplaces and tags; one «Только в наличии» checkbox; sorting first among sidebar filters with deal-first default and ascending/descending price only; deal labels «Все предложения», «Выгодные», «Невыгодные». Tags default to all and match OR. User explicitly confirmed: «Наличие это чекбокс. один чекбокс “Только в наличии” … Теги по умолчанию все. Товар тожен содержать хотя бы один. Теперь сделай новое демо».

Replace the two-layout comparison with the selected refined preview, retaining one catalog and bottom status. Keep the changes demo-only. Use compact multi-select checkbox popovers to preserve vertical space. Add two mock marketplace samples and meaningful tags through existing mock import/update operations; no persisted data or live services are involved.

## Verification plan

Type check, frontend unit suite, relevant catalog/layout E2E plus new variant/collection flows; production frontend build. Browser plugin is not available, so rendered validation uses Playwright. Inspect 1440×900 and minimum supported 1024×768; mobile is outside the desktop product's minimum width.

## Entry

Run `npm --prefix frontend run dev:demo`. Open `http://127.0.0.1:5176/cards?sidebar=2`. Data and desktop-only dialogs are simulated. The mock collection pauses for verification; use «Проверка пройдена» to continue. Marketplace/tag popovers default to all. Bulk buttons select all or clear tags/keep one marketplace; the last marketplace checkbox is disabled until another is selected. Empty tags display «Без тегов» and show untagged products (LEGO in the sample).

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

## Heading and selection revision

User authorization: «Обязательно хотя бы 1 маркеплейс, можно не выбирать теги (тогда подпись - без тегов). Остальное верно. Поправь демо». Add heading «Карточки товаров» above search. Popups retain individual checkboxes and one bulk button, without repeated visible headings or common-selection checkboxes. Tags use «Снять выбор / Выбрать все»; marketplaces use «Оставить один / Выбрать все» to describe the required minimum honestly. Empty/invalid marketplace URL selections normalize to all. Empty tags filter untagged products; the sample LEGO card now has no tags. These changes remain inside the mock preview.

Verification of this revision:

- `npm --prefix frontend test`: 113 tests / 22 files passed, including updated empty-tag and invalid/empty marketplace semantics.
- `npm --prefix frontend run test:e2e -- sidebar-demo.spec.ts`: 7 passed. Covers heading, multi-selection, bulk actions, last-marketplace protection and re-enabling, «Без тегов» filtering/reload, filter combinations, dialogs, sorting and collection verification at 1440×900 / 1024×768.
- `npm --prefix frontend run desktop:build`: passed (includes TypeScript check and frontend build), release binary built.
- `openspec validate demo-sidebar-layouts --strict` and `git diff --check`: passed.
- Playwright visual inspection at both desktop sizes: heading above search, individual checkboxes, no repeated popup headings, honest bulk button labels, protected last marketplace and one LEGO result for «Без тегов». Page identity/content/overlay/console checks passed, with no page or console errors. Images were inspected with `view_image` and remain in `/tmp/sidebar-selection-*.png` outside the repository. Browser/IAB unavailability is unchanged from prior verification.
- Repowise live-diff review flags MultipleChoice complexity; manually reviewed required/optional selection branches and URL normalization against the passing unit/E2E cases. Its stale dependency recommendation remains inapplicable: no dependency changes occurred. This is a localized demo revision; the prior 52-case production catalog regression evidence is retained above, not claimed as rerun for this revision.

Remaining boundary: mock-only preview, no live service/native WebView testing or data migration. Stage only this revision, inspect the staged diff, commit and present for evaluation; do not archive yet.

## Popup styling correction

User requested that the lists fit within the sidebar and their bulk action sit on the left, styled like «Создать группу». The standard Popover width and ghost/self-end button caused the prior appearance. Changed only the preview's popup width to the Radix trigger-width variable and the bulk button to the shared default-size outline variant, full width with left-aligned text.

Validation: seven existing sidebar-demo E2E cases passed; `npm --prefix frontend run build:desktop` passed, including TypeScript. Playwright measured both popups at 212 px, matching their triggers and remaining inside the 260 px sidebar, at 1440×900 and 1024×768. Buttons measured 192 px inside popup padding, used the outline variant and computed `justify-content: flex-start`; clicking retained the existing selection behavior. No page or console errors. Inspected `/tmp/sidebar-popup-*.png` using `view_image`; screenshots/scripts remain outside committed source. The temporary geometry script was corrected to wait for opening animations and scope to the open popup rather than its closing predecessor. Selection logic and production desktop controls are unchanged. Unit and full native builds were not repeated for this two-line presentation correction.

## Counter and compact bulk buttons

User corrected the prior interpretation: the bulk button must not fill the popup. It now uses the shared small outline variant with `self-start`, sizing to its text. The catalog's existing matching/total count moved beside the heading with exact wording «Выбрано n из m товаров» and was removed from the demo view bar below search; normal desktop rendering/counting is preserved.

Validation: seven existing sidebar-demo E2E cases passed; `npm --prefix frontend run build:desktop` passed including TypeScript. Playwright confirmed one counter on the heading's right, vertically centered, absent below search, updating from «Выбрано 7 из 7 товаров» to «Выбрано 1 из 7 товаров» on search. At 1440×900 and 1024×768 popups remain 212 px, action buttons are 28 px high and about 110 px / 99 px wide, left aligned. No page or console errors or horizontal document overflow. Inspected `/tmp/sidebar-compact-*.png` with `view_image`; QA scripts/images stay outside committed source. No selection logic, API, persistence or production desktop behavior changed; no unit/native build rerun was needed for this presentation-only correction. Commit the reviewed task files before user evaluation; acceptance/archive remain pending.

## Left-side add-card panel

User authorization: «При нажатии добавить карточку, панель должна появляться слева». Added an optional left/right side to the shared drawer wrapper, retaining the right default. Both preview entry points (global action and catalog empty state) request left. Existing creation fields, validation, persistence commands, edit/default desktop placement and focus restoration remain unchanged. Explicit left-side width classes preserve the existing 420 px form width over the primitive's different left defaults.

Verification: the 15 existing AddCardDrawer/CardDrawer tests passed; all seven sidebar-demo E2E cases passed; `npm --prefix frontend run build:desktop` passed including TypeScript. Playwright verified catalog entry at 1440×900 and 1024×768 with x=0, y=0, width=420 and full viewport height, Escape closure and focus returning to «Добавить карточку». Product-details entry also opened left and closed using «Отмена». No page/console errors. Inspected `/tmp/sidebar-left-add-*.png` with `view_image`; temporary QA stays outside the repository. No live services, user data or database/native runtime changes were involved. Commit the checked revision before user evaluation; do not archive until accepted.


## Compact catalog list

User authorization: move list/grid controls left, retain only marketplace marks in the marketplace column, keep checkboxes before photos and reduce unnecessary horizontal gaps while preserving equal row widths. The mock preview now uses one fixed 1012 px table grid instead of a viewport-stretched table (1124 px at 1440 viewport). Column widths and 8 px cell padding apply consistently to products, groups and headings; the table stays inside its horizontal scroll container. The first 32 px column centers selection before the photo. Marketplace names are visually hidden only in demo table cells and remain accessible; marks have hover titles. Shared desktop list layout and grid labels are preserved.

Verification: `npm --prefix frontend run build:desktop` passed including TypeScript; all seven existing sidebar-demo E2E cases passed (45.6 s), including view switching and group creation; OpenSpec strict validation and diff whitespace checks passed. Playwright at 1024×900, 1440×900 and 1920×900 measured every rendered product row at 1012 px, view controls at the table's left edge, checkboxes between row edge and photo, 1 px visually hidden labels, no document overflow, framework overlay or page/console errors. Checkbox selection and deselection worked. Inspected `/tmp/sidebar-density-1440.png` and `/tmp/sidebar-density-1024.png`; temporary scripts/screenshots stay outside the repository. Browser plugin not available; regular Playwright used as recorded earlier. At 1024 px, horizontally scroll the list to reach all metric columns. This remains a mock-only demo; live services and native WebView were not tested. Acceptance/archive remain pending.


## Action spacing, centered metrics and tile typography

User authorization: give the three-dot menu room at the right edge, use equal price sizes in tiles and muted regular «Сейчас не выгодно», center headings/content from marketplace onward and add breathing room around unavailable statuses. The preview action column is now 56 px and availability 144 px, with the sticky offset updated together. Table width is 1060 px on wide desktop and 980 px at <=1200 px (220 px identity column), keeping current price visible before the pinned availability column. Every row shares the same grid. Header utility alignment explicitly follows the centered cells. Tile numeric prices use 14 px; absent-deal text uses muted 13 px / weight 400 as in the list. All styles remain scoped to the demo.

Verification: seven existing sidebar-demo E2E cases passed (45.8 s). Frontend desktop build including TypeScript passed, with a final rerun after header alignment. Focused Playwright at 1440×900 and 1024×900 checked centered header/cell styles, uniform widths, action-button containment (~13 px outer spacing), >=8 px around all availability badges, current price staying clear of pinned availability, opening/closing the action menu, 14 px tile price values and 13 px / 400 muted non-deal captions. No page/console errors. Screenshots `/tmp/sidebar-spacing-list-*.png` and `/tmp/sidebar-spacing-grid-*.png` inspected; QA artifacts remain outside the repository. Browser plugin absent; regular Playwright used. Mock data only; no service/native runtime/data changes. Commit before review; acceptance/archive pending.


## Application display name

User clarified that the app is «Price watch» and «price-watch» is the development/repository name. Updated the normal/demo brand, browser/window titles, startup caption, tray caption, native error caption and product display name. Technical package/binary names, application identifier, local storage keys, filesystem paths and export format remain unchanged. Existing E2E document-title expectations now use the display name. The user asked whether prices/status have matching sizes: rendered measurements are 14 px / 14 px in list and 14 px / 12 px in tiles; no typography change was requested or made in this revision.

Playwright confirmed the brand and document title in both normal mock UI (5175) and sidebar demo (5176), with no page errors. Screenshot `/tmp/sidebar-price-watch-brand.png` inspected. Browser plugin absent; used existing Playwright. `npm --prefix frontend run desktop:build` passed including TypeScript, frontend and Rust release compilation; output binary remains `target/release/price-watch`. All seven sidebar-demo E2E cases passed (55.9 s). Diff whitespace checks passed. Full title-assertion suites were updated but not rerun; normal mock title/brand were directly checked in Playwright. Native window/tray were compiled but not launched. Acceptance/archive remain pending.


## Consolidated audit before production implementation

User requested a review of all accumulated changes so nothing is forgotten at adoption. Reviewed the nine implementation commits `e3734c3..5d92d7d`, current source, preview delta-spec/design/proposal/tasks, all user decisions and existing test coverage. Added `docs/guide/SIDEBAR_IMPLEMENTATION_CHECKLIST.md` as the consolidated handoff: final labels/semantics/layout/typography, implementation source map, real-service wiring, removal of replaced demo/old-layout branches and production acceptance checks. No application code or OpenSpec artifacts changed during this audit; no production activation, spec sync or archive.

Findings requiring attention at adoption: count is currently catalog entries (one per group), not checked cards or raw product count; group filters and available tags use representatives; navigation by brand resets URL filters; Chrome/settings are simulations and shell service-error/retry integration must be retained. Historical tasks/design/proposal do not enumerate every later revision; the handoff explicitly records the final heading, compact rows, left form, title and fonts. No request to equalize the tile availability font with its prices was made.

Repowise live-git review covered the full range; it reports structural complexity in preview filter/layout branches and unsupported CSS analysis, not demonstrated runtime defects. Current source was inspected for ownership, URL semantics and mock isolation. Index metadata remains 12 days old at `9f3876d9` despite earlier CLI refreshes; the dependency recommendation is stale (the actual audited range has no package-lock change). Did not use its affected-test list as authoritative.

Audit validation: all 113 frontend unit tests / 22 files passed. Reused focused Playwright geometry/typography and left-drawer QA against the current preview: aligned headers/cells, equal row widths, ~13 px action spacing, availability badge padding, uniform tile numeric sizes/muted non-deal text, left 420 px form at both supported widths, detail entry and focus return passed without page/console errors. OpenSpec strict validation and diff whitespace checks passed. Browser plugin unavailable; regular Playwright used. Native build passed on the unchanged implementation at `5d92d7d` in the preceding revision; not rerun for this documentation-only audit. `npm --prefix frontend run test:e2e -- sidebar-demo.spec.ts app.spec.ts layout.spec.ts usability.spec.ts`: all 53 cases passed (3.5 min), covering demo plus normal catalog/layout/usability. Existing lazy-route `No HydrateFallback element provided` warnings remain; no new failure was observed. Live services/native WebView are outside the mock checks.


## Approved group/count/navigation decisions recorded

User approved the proposed container model and requested «Хорошо. Закрепи это». Updated the existing proposal/design/spec/tasks and implementation checklist; this is documentation only. Filters apply to individual group members with the full predicate on the same card, groups with zero matches disappear, expansion contains matching members and summary shows matching/total members. The representative is the first matching card in the selected order. Tag discovery includes all cards. Global matching/total counts count each individual card once, independent of collapsed state or bulk checkboxes. Price watch becomes noninteractive text; the explicit details return link preserves catalog context.

The previous representative-only/entry-count/clickable-brand behavior remains in code and is explicitly marked as an implementation gap. OpenSpec section 5 is unchecked; earlier completed demo tasks remain historical evidence. No application code, production activation, spec sync or archive was performed. Authorization to record these already-approved decisions does not claim they are implemented. Validation: strict OpenSpec and whitespace checks; application tests not rerun for documentation-only edits.
