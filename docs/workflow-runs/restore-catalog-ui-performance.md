# Restore catalog UI performance

## Status

2026-11-06: user explicitly approved the concrete plan with «да», then requested continuation and compact updates. Implementation verified under openspec-apply-change; ready for user evaluation after the task commit. Separate acceptance gate remains pending. Planning commit: 06fd2f2.

OpenSpec: `restore-catalog-ui-performance` (proposal, design, catalog-snapshot delta, tasks).

## Established evidence

- Current baseline commit: `72a1356`, accepted sidebar implementation. Working tree was clean before planning.
- Sorting regression is in catalogModel: localeCompare with numeric language options per comparison, repeated sort parsing and sorting the matching/final sequences. The old implementation reused a collator.
- Release Chromium mock exploratory timing on 5000 seeded randomized names: median title sort ~217 ms and active-sort search ~205 ms; runtime-only cached-collator experiment ~87/60 ms. These are 10 post-warmup samples including automation/two frames, not formal p95 acceptance evidence or an implemented fix.
- Virtualization remains bounded: 12-15 table rows at 5000 products; last item reachable; grid switching works. No page errors in exploratory checks.
- Instrumented development run: 30 progress counter updates caused 60 AppShell/CatalogFilters/AddCardDrawer calls with StrictMode double invokes, while catalog rows were unaffected. This demonstrates unnecessary work, not native timing impact.
- Urgent search changes immediate returnTo while only model params are deferred; fresh result callbacks also defeat memo boundaries. Entire URL params trigger model rebuilding on view-only changes.
- Existing 8 performance E2E and 8 focused catalog unit tests passed during investigation. Performance E2E checks DOM/behavior, not latency. Existing benchmark search selector is obsolete.
- Repowise MCP continues serving a 12-day-old snapshot despite a local incremental index-only update; rely on current source/Git for recent history and report this limitation. CodeGraph served current source with the explicit project path.

## Plan and acceptance

1. Repair and extend the benchmark/fixture, document commands and capture a matched unoptimized release baseline before runtime changes.
2. Prepare comparison/snapshot data once, reduce sorting, remove duplicate tag work and isolate model dependencies from view-only URL state.
3. Restore coherent deferred results/navigation and stable callbacks, with rapid-action/navigation coverage.
4. Refine the existing collection provider split to keep progress counters out of sidebar/form subscriptions, retaining locks/errors/completion updates.
5. Run semantic/render tests, full frontend checks, desktop build, paired release benchmarks and visual QA; commit implementation before user evaluation.

Acceptance follows catalog-snapshot budgets (p95 <=200 ms; >=30% improvement for actions whose matched baseline exceeds 200 ms), using 100/1000/5000 seeded heterogeneous plain/mixed/group data, 5 warmups and 30 samples per action. Preserve all accepted column/group/filter/count/price/navigation behavior, bounded DOM, focus and collection locks. No new dependency, API change, migration or user-data operation; backend/worker/CLI/database-free numeric mode remain outside changed code.

## Checks

Planning-only validation results and commit are reported in the conversation. Runtime checks above were executed during investigation against unchanged application code; they are not post-implementation results.

## Next action

Wait for user evaluation of the verified implementation commit. After implementation and commits, request acceptance; sync/archive only after acceptance.

## Implementation progress

User approval: «да» after plan commit 06fd2f2. Using change restore-catalog-ui-performance, spec-driven (14 tracked tasks).

Repaired benchmark selectors and disambiguated group actions; added seeded opt-in varied mock dataset while preserving uniform E2E fixtures. Fixture determinism test, budget unit test, typecheck and existing 8/8 performance E2E passed. Captured isolated unoptimized HEAD frontend plus identical fixture at /tmp/price-watch-ui-baseline-sm_ydn9e/frontend, built to /tmp/price-watch-ui-before, served on 5177. Formal baseline /tmp/price-watch-ui-before.json has all nine cases, 5 warmups/30 samples; command exit 1 is expected because it correctly detected 15 budget failures, all at 5000 cards. Title-sort p95 up to 263 ms; active-title search up to 253.5 ms; view changes up to 281.7 ms. No app errors. Application/runtime edits do not affect this isolated baseline build. No other heavy tests/builds ran during timing; one short typecheck ran during the early small-data phase. Raw reports/screenshots remain outside the repo.

Implemented comparator preparation, snapshot/filter memo boundaries, flat-sort reuse, deferred coherent results and stable callbacks (including a committed-setter bridge because React Router's setter changes with search), and a separate collection action/lock context. Added semantic, hook, suspended-render, sidebar/form isolation and rapid-navigation E2E coverage. Validation results are recorded below.

## Verification before paired after timings

- `npm --prefix frontend run lint`: passed; native build also reran TypeScript.
- `npm --prefix frontend test`: final 103/103 tests in 27 files passed. The initial new suspended-render test used MemoryRouter, whose transition behavior differs from the application's Data Router/flushSync. Corrected the test to createMemoryRouter/RouterProvider; no application workaround was added.
- `node --test scripts/benchmark_ui_metrics.test.mjs`: passed, including exact percentile, absolute/improvement budgets, failures, missing baseline and regression visibility.
- Full mock E2E: 74/77 initially passed. Two pre-existing assertions still required zero sortable-header buttons despite accepted column sorting; updated to seven total/one savings button and added price aria-sort assertion. The new focus scenario initially targeted an offscreen group in a mixed fixture; corrected it to an initially visible single-group fixture. Targeted rerun including those fixes, rapid search and a newly added same-task deferred-search/link navigation scenario: 5/5 passed. Thus all 78 distinct final scenarios were exercised successfully against unchanged application runtime source across the full and targeted runs. No new application failures were found. Existing No HydrateFallback warning remains; it predates this change.
- `npm --prefix frontend run desktop:build`: passed TypeScript, Vite and Rust release (31.56 s Rust build). Checked all four desktop JS assets for __pwPerf/installPerformanceFixture/uniform fixture names/dataset markers: absent. No native app launch, API, worker, Chrome, database or user data used; no backend files or migrations changed.
- Browser plugin not available; used installed Playwright, release mock at 127.0.0.1:5178, 1440x900 and 1024x768. Verified page title/URL, meaningful UI, no Vite error overlay or console/page errors, title sort, stock filter, grid/list and modal draft/focus across 30 counter updates, including focus restoration. Screenshots /tmp/price-watch-ui-list-{1440,1024}.png and /tmp/price-watch-ui-grid-{1440,1024}.png; list-1440 and grid-1024 visually inspected. Document fits both widths; rendered grid cards bounded at 24/15 respectively. Existing eight E2E cover last-item access, scroll restoration and keyboard/menu ownership.
- Repowise live diff: no high/critical introduced findings. Two medium complexity advisories in comparator/filter normalization and a low CardsPage-size advisory reviewed against current source and branch/semantic tests. Its 12-day-old graph falsely attributes dependency changes from older history; package manifests/lockfiles are unchanged in this task. Do not treat inferred affected tests as complete. Full frontend suites were run.
- Strict OpenSpec validation and whitespace check passed before final record updates; repeat before commit.

Paired after timings completed with no simultaneous build/test load. Baseline/after reports are /tmp/price-watch-ui-{before,after}.json; both use isolated mock release builds, fixed seed, Chromium, viewport and action matrix. Native p95 remains unmeasured.

## Final release results

All 189 per-action budgets passed across nine datasets; paired after command exited 0. Maximum after p95: 98.9 ms. Baseline had 15 failures at 5000 cards. Five warmups and 30 samples per action, Chromium 153.0.8010.12, 1440x1000, seed 42, 12th Gen Intel(R) Core(TM) i5-12450H. Every column/direction, title-search, selection, views, group controls and progress were measured. No app errors. Raw per-action p50/p95, samples, DOM, heap and long tasks, thresholds and regressions are retained in /tmp/price-watch-ui-before.json and /tmp/price-watch-ui-after.json.

| Cards | Shape | Initial DOM nodes | Used JS heap (MiB) | Max after p95 (ms) |
|---|---|---:|---:|---:|
| 100 | plain | 582 | 42.6 | 98.9 |
| 100 | mixed | 616 | 29.8 | 73.3 |
| 100 | group | 616 | 42.6 | 98.3 |
| 1000 | plain | 580 | 31.6 | 85.1 |
| 1000 | mixed | 620 | 22.0 | 86.9 |
| 1000 | group | 612 | 17.4 | 78.2 |
| 5000 | plain | 614 | 35.6 | 76.0 |
| 5000 | mixed | 619 | 19.6 | 81.9 |
| 5000 | group | 614 | 42.6 | 90.7 |

5000-card plain dataset, milliseconds:

| Action | Before p50 / p95 | After p50 / p95 |
|---|---:|---:|
| sort:title:asc | 215.4 / 263.0 | 36.7 / 40.1 |
| search:title | 218.9 / 249.5 | 44.7 / 58.6 |
| grid | 233.4 / 281.7 | 49.6 / 50.7 |
| list | 233.0 / 280.1 | 49.3 / 50.5 |

All tracked tasks verified. Staged source diff reviewed; no unrelated edits, dependency changes, backend/API/worker/CLI changes, migrations or persisted-data operations. Strict OpenSpec and staged whitespace validation passed. Commit the verified implementation before evaluation. Await explicit user acceptance; only then sync specs/archive and commit closure. Native WebView p95 remains unmeasured; browser release timing and desktop build are separate evidence. No push/merge.

## User evaluation revision: sort arrows on the left

User requested arrows to the left of each column name. Updated CatalogColumnHeaders to a horizontal icon/label layout, with compact 12 px icons and labels. Added optional Russian soft-hyphen breaks for the two long single-word labels so arrows and text remain separate in the existing compact widths. Accessible button names, aria-sort and sorting behavior are preserved. This is an explicitly authorized local presentation revision; acceptance of the overall performance change remains pending.

Validation: typecheck, all 103 unit tests and the existing seven-column ascending/descending/sidebar/URL E2E passed. Playwright mock visual QA at 1440x900 and 1024x900 verified icons geometrically left of every label and no page errors; screenshots /tmp/price-watch-sort-left-{1440,1024}.png, 1440 screenshot inspected. Browser plugin unavailable; used installed Playwright. Final header-wrap checks passed: typecheck, 103/103 unit tests, 1/1 E2E covering every column in both directions, and desktop release build (24.92 s Rust compile). No performance model or persisted data changes; no rerun of the full benchmark matrix for this presentation-only adjustment.

## User evaluation revision: participation filter and ordering

User requested a second deal-filter option and a checkbox after stock, plus verification that participating products precede excluded products before sorting by savings. After rejecting the ambiguous standalone «участвующие», the user explicitly approved «Участвуют в выгодных предложениях» and «Сначала товары, участвующие в выгодных предложениях» with «Да», then requested continuation. This is an authorized scoped evaluation revision; overall acceptance remains pending.

Added `deals=participating`, based on dealsEnabled rather than current profitability. Added default-on priority with URL opt-out `participationFirst=0`; reset restores default. The prefix applies to every column, members and UI representatives. Default comparison is participation, exact descending savings, availability, price and stable kind/ID. Disabling the checkbox removes the participation prefix. Missing money remains last within each enabled/disabled block or globally without the prefix. URL/model memo key, reload and details context include both controls. Updated sidebar/group spec deltas and UI/design/proposal documentation; no API, worker, CLI, dependencies, migration or persisted-data operation.

Verification so far: 106/106 unit tests, typecheck and desktop release build passed (32.93 s Rust compile). No performance fixture markers in desktop JS assets. Visual QA via installed Playwright (browser plugin unavailable), 1440x900 and 1024x768: checkbox wraps legibly; second dropdown option fits; no document overflow or page errors. Screenshots `/tmp/price-watch-participation-{1440,1024}.png` and `/tmp/price-watch-participation-options-{1440,1024}.png`; 1024 option screenshot inspected. The paired release timing matrix above predates this refinement; it was not rerun and does not measure the new participation comparator. Existing bounded-catalog/performance E2E is included in the current full run. Native WebView runtime remains untested.

Repowise live diff examined the current application edits. Two structural complexity advisories rose to high (15 branches in CatalogFilters and selectCatalogItems) after adding the filter condition; reviewed the actual conditions, control wiring and coverage rather than treating these as proof of a defect. All effective filter and checkbox transitions are exercised by unit/E2E checks. No unrelated refactor added. Its graph remains 12 days stale and incorrectly attributes older dependency changes to the task; manifests/lockfiles are unchanged here. Full frontend suites used instead of inferred test selection.


Final revision checks: full mock E2E initially 74/79 passed. Four assertions required adjustment: old tests assumed global column ordering, and the first new test wrongly assumed Dyson was excluded (the fixture actually excludes LEGO). Corrected expected list/grid/member order and test inputs; group E2E now verifies immediate participating-representative replacement, then the previous representative when the prefix is disabled. The fifth failure was a transient 1024-width measurement in unchanged variant-images; it passed without source changes. Targeted rerun of all five scenarios passed 5/5 (25.2 s), exercising all 79 final scenarios across these runs against unchanged application source. No claim of a single clean full run. Final typecheck, strict OpenSpec and whitespace validation passed. Revision ready for commit and user evaluation; do not sync/archive until acceptance. No push/merge.
