# Sidebar layout demos

## Plan and authorization

2026-11-05: user approved implementing a UI demo with two variants after reviewing the sidebar proposal. Keep one catalog. In both variants global actions move into a permanent sidebar; collection status appears across its width at the very bottom. Variant 1 retains catalog search/filters/sort/group creation; variant 2 moves these into the sidebar. Use existing UI and isolated mock data.

User message: «Хорошо, реализуй демо версию как это будет на ui. А также вторую версию где ты перенесешь фильтры, создание групп, сортировку в панель».

## State

First iteration committed as `1d1663e`; selected-layout refinement as `58324da`; heading/selection revision as `9fe3ade`; popup-width revision as `77ffa59`. User requested a single count beside the heading and compact content-width bulk buttons. This correction is implemented and verified; preparing its commit for evaluation. OpenSpec: `demo-sidebar-layouts`. Explicit acceptance of the current revision and production adoption are pending. Do not sync/archive yet.

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
