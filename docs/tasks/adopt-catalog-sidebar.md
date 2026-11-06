# Permanent catalog sidebar

## Authorization and plan

2026-11-06: User approved the iterated demo and explicitly requested «ПРиступай к переносу». This authorizes implementing the documented production-transfer checklist, not enabling the mock shell. Using vibe-flow and OpenSpec adopt-catalog-sidebar. No new product scope beyond the approved demo and real runtime wiring. Production transfer plan is captured in proposal/design/tasks and the existing checklist; implementation is authorized by this request. User evaluation remains required after implementation and commit.

The shell owns global add/group/import/refresh and real desktop tools; catalog filtering is permanent and single-model. Filters on details retain the saved catalog context and take the user to matching results when changed. No database/schema/API/worker/CLI change. Preserve unrelated whole-ruble-display.md edits.

## Verification plan

Typecheck, unit tests, mock E2E, desktop production build and list/grid visual checks. Browser plugin not available; use existing Playwright. Mock checks do not validate live services or native WebView. Repowise MCP index is 12 days stale at 9f3876d9; use current source and tests for critical claims. CodeGraph current source was read for shell/settings/catalog/filter paths.

## State

Accepted and closed on 2026-11-06. Specs synchronized; change archived at `openspec/changes/archive/2026-11-06-adopt-catalog-sidebar/`. Verification history follows.

## Implemented changes

The permanent AppShell now owns global add (left drawer), create-group, refresh, import/export, real Chrome invocation, real BackgroundSettings and runtime recovery alerts. Catalog filters are controlled by the shell on both routes; details use the validated returnTo context and changing a filter opens those catalog results. There is one collection panel and one catalog model. CardsPage retains bulk creation/editing and passes original group membership to the editor. The brand is inert.

Moved useful preview controls/model/tests to features/cards and test fixtures to src/test; removed features/sidebar-demo, lazy mock shell, portal contexts, fake settings and environment/query UI switches. Removed old single-filter and column/update-sort code and tests; kept current card savings and default-order tests. Main fixture code is E2E-only and explicitly excluded with the desktop flag. No runtime services, database, worker, Python or Rust code changed; technical names/history/schema are preserved.

## Review findings and corrections

Repowise live diff review (stale 12-day index) flagged structural complexity in AppShell and moved filtering/comparison functions. Reviewed command guards, error paths, contextual filters, group projection and stable sorting; exact-decimal and per-member tests cover the branching. The dependency/package-lock warning comes from older history, not this task. Static analysis is not live desktop evidence. Existing mock E2E and performance scenarios are run in full because shared shell/styles changed.

Initial E2E run: 67/74 passed. Remaining assertions encoded removed column/single-state filters, old labels, old representative, old nondeal text size or selected the new global refresh instead of detail refresh. Updated them to the approved UI rather than preserving obsolete behavior. One progress scenario lost its panel during a Vite page reload while main.tsx was edited during the run; the final suite is run against unchanged source to distinguish HMR interference from a regression. The other progress viewport and all eight large-catalog/performance scenarios passed. First targeted suite passed 12/13; the last was still checking fake desktop tools and was replaced by permanent action/context checks.

Final unit run: 95 tests in 23 files passed (the prior 116 count included superseded column/object-filter tests; remaining approved semantics coverage was moved, not dropped). New AppShell tests verify Chrome command/pending/error, collecting locks, one progress mount and runtime recovery. Existing background settings tests verify real command names through mocked invoke.

Visual QA: Browser plugin not available, using existing Playwright at 127.0.0.1:5176. Confirmed Price watch title, meaningful UI, no framework overlay or console/page errors. Exercised group creation, member filter, collapse/expand and list/grid at 1440x900 and 1024x768. Rows measured uniformly 1060/980 px; document overflow contained, group metrics 14 px, nondeal text 13 px/400. Inspected /tmp/adopt-sidebar-list-1440.png and /tmp/adopt-sidebar-grid-1024.png. Temporary screenshots/scripts/logs are outside the repository.

Final typecheck passed. Final E2E and desktop build results are recorded below. Native WebView/live Chrome/registration/quit/API/worker were not launched; a build and mocked-invoke tests do not verify these integrations live. User acceptance, spec sync and archive remain pending.

Final native production build passed: TypeScript, Vite frontend and Rust release binary at `frontend/src-tauri/target/release/price-watch` (53.12 s native compile). Strict OpenSpec validation and whitespace checks passed. The native command registrations were verified in current Rust source: open_store_browser, get_background_state, set_background_enabled and quit_app remain unchanged.

## Recovery during final verification

The tool server restarted after the final E2E run completed the first 54 scenarios without failures and entered the sidebar tests. The Playwright runner was terminated, leaving only its Vite child. Confirmed no commit had been created, preserved staged changes, stopped only that known Vite PID and resumed the remaining test files. The resumed selection runs 21 tests (including the Ozon variants test already completed in the first segment). No application code changed between these segments. Both 1440/1024 progress/challenge scenarios now passed, supporting the earlier HMR diagnosis. The known pre-existing React Router No HydrateFallback warning remains; no new application console/page errors were observed in visual QA.

## Final verification

- `npm --prefix frontend run lint`: passed.
- `npm --prefix frontend test`: 95/95 tests in 23 files passed.
- `npm --prefix frontend run test:e2e`: first 54 scenarios completed without failures before infrastructure interruption; remaining test files rerun with `-- sidebar.spec.ts usability.spec.ts variant-images.spec.ts variants.spec.ts wildberries.spec.ts`: 21/21 passed (1.9 min), including one repeated Ozon scenario. All 74 distinct scenarios in the suite were exercised successfully against the final source across these segments. Includes eight 5000/1000-card virtualization and performance scenarios.
- `npm --prefix frontend run desktop:build`: passed TypeScript/Vite/Rust release build.
- `openspec validate adopt-catalog-sidebar --strict` and staged whitespace checks: passed.
- Visual Playwright QA: list/grid, 1440x900 and 1024x768, uniform widths and group fonts, no page/console errors or framework overlay; screenshots inspected.

Preview server is running at http://127.0.0.1:5176/cards (normal mock catalog) or /cards?fixture=catalog (expanded test fixture). Both use the permanent UI. No live API/database/worker or native WebView/Chrome/OS registration was launched. Scope is frontend only, no migration. Preserve the unrelated `docs/tasks/whole-ruble-display.md` working-tree edit. Commit all task changes before evaluation; do not push, sync or archive pending user acceptance.

## User review adjustments: columns, settings, progress and filter order

The user requested swapping Marketplace and Savings columns, aligning Settings with the sidebar tools, restoring the collection panel to its former bottom-right location and dimensions, then ordering filters as stock → sorting → deal status → marketplaces → tags and moving Reset to the right of the view switcher. These are authorized localized UI revisions; implementation acceptance remains pending.

Changed table headers, product/group cells and corresponding widths together. Settings now explicitly uses `justify-start`, overriding the Button default utility that previously beat the sidebar CSS. Removed the sidebar progress wrapper and all of its sizing overrides; the existing fixed collection panel once again uses 490 px width, 28 px right/bottom insets and viewport-limited height. Reset remains conditional and preserves the selected view. No service, persistence or API changes.

Verification:
- Typecheck and all 95 unit tests passed; typecheck also passed after the final filter/reset rearrangement.
- Initial relevant E2E selection: 17/19 passed; two group tests still used the former savings column index. Updated these and the equivalent app assertion. Targeted rerun of both group scenarios plus the app offers scenario: 3/3 passed.
- Browser plugin not available; used installed Playwright with mock data. Visual QA at 1440×900 and 1024×900 verifies header/cell order, filter order, conditional Reset placement and view preservation, Settings/Chrome icon alignment (both x=23), settings popup, and panel width=490 with 28 px right/bottom insets. No page errors. Screenshots `/tmp/sidebar-review-1440.png` and `/tmp/sidebar-review-1024.png` inspected. Desktop tools exposed only through temporary Playwright route interception, Tauri invoke mocked; no production/demo mock branch added.
- Repowise live diff analysis found no introduced structural findings. Its 12-day-old index still names historical dependency changes and skips CSS; reviewed current diff and CSS manually rather than treating that test-selection inference as current evidence.
- Strict OpenSpec validation and whitespace checks passed. Specification/checklist updated; no sync or archive.

Final verification after the filter/reset adjustment: desktop release build passed (40.31 s Rust compile). Sidebar E2E rerun: 8/9 passed; the bulk-tags scenario timed out while an animated popup detached during click. The same scenario passed unchanged in an isolated rerun (1/1, 8.2 s); direct Playwright reproduction at 1280×720 also passed. This remains an intermittent browser timing observation, not a reproduced functional defect. Across the selections, all 20 relevant distinct E2E scenarios passed (19 sidebar/layout/group scenarios plus the app offers scenario), with the reruns described above. No live desktop services or user data were used. Final changes are ready for user evaluation; no push, spec sync or archive.

## User review: restore column sorting and clarify count

User requested restoring clicks on column headings and changing the matching count to «Показано n из m товаров». Restored all seven data headers with ascending/descending toggles, visible arrows and aria-sort. A single URL sort controls headers, the sidebar, individual cards, group representatives and member order. Sidebar retains three primary choices and shows the active column sort when needed. Explicit sorts ignore deal priority; missing money stays last in both directions, unknown availability sorts with out-of-stock. Bulk-selection and multi-choice selection labels still say «Выбрано», since those describe actual selections.

Verification: all 96 unit tests passed; final targeted mock E2E selection passed 2/2 (all seven headings in both directions, URL/reload/sidebar synchronization, stock and deal filters, price ordering). Typecheck and strict OpenSpec validation passed. Browser plugin not available; used installed Playwright. Inspected `/tmp/price-watch-column-sorting.png`, moved arrows below labels to prevent overlap in compact columns; final screenshot inspected, no page errors. Repowise live-diff complexity findings reviewed: extracted column-header rendering and sort-value projection to keep added branching out of the main results component and comparator. Its historical index remains 12 days stale; dependency/test-selection hints refer to prior commits, with no dependency changes in this task. No live API, database or native runtime tested. Planning artifacts updated to current user instruction; no sync/archive pending acceptance.

Final desktop release build passed (TypeScript/Vite/Rust; 1m07s Rust compile). Post-extraction Repowise review of sorting/results/parser reports only a medium complexity advisory for the small column-header renderer; no remaining high/critical new findings in those files. Reviewed its finite column/direction branches against the passing browser scenario. Changes ready for user evaluation.

## Acceptance and closure — 2026-11-06

User accepted the implementation with «Окей эту задачу закрывай» after commit `db343c2`. Synchronized catalog-sidebar (new capability with authored Purpose) and group-card-metrics (all six updated requirements, retaining established Purpose and scenario names). Corrected the remaining obsolete savings-sort scenario to match the accepted clickable headers. Verified every delta requirement against main specs before moving the change to `openspec/changes/archive/2026-11-06-adopt-catalog-sidebar/`.

`openspec validate --specs`: 17/17 passed, with description-length advisories in collection-run-execution (pre-existing) and group-card-metrics. Strict change validation passed before archive. Application code is unchanged since the accepted implementation and its recorded checks; no repeat runtime tests needed for this documentation-only closure. No push or merge. Task complete.
