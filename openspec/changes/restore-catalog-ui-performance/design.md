# Design

## Context

See proposal.md for measurements and scope. Current `buildCatalog` filters/sorts cards, groups them, then sorts the top-level projection again. The comparator parses sort settings and constructs locale comparison options per comparison. `useCatalogModel` depends on the entire URLSearchParams object. `CardsPage` defers model parameters but immediately changes `returnTo` and passes fresh result callbacks. AppShell consumes full collection state and recreates filters/forms on every progress update. Existing virtualization is working and must be retained.

## Goals / Non-Goals

**Goals:** Keep accepted sidebar/group behavior while reducing main-thread work; make performance and render isolation reproducible and testable.

**Non-Goals:** Visual redesign, backend/API/cache changes, a new global state library, new dependencies, workers for sorting, persisted-data changes, or claiming browser timing proves native WebView performance.

## Decisions

### Prepare comparison and snapshot data once

Create a comparator per effective sort using one module-level Russian numeric collator. Keep exact decimal money comparisons, stable kind/ID ties, missing money last in both directions within the selected participation scope, and availability semantics as refined below. Prepare card projections, group lookup and available tags when snapshot data changes. Parse stock/sort/filter options outside item loops. Remove the unused duplicate tag preparation in the model or share the existing pure preparation with the sidebar, leaving one owner per consumer.

Filter cards before grouping so conditions cannot be satisfied by different group members. Sort the matching sequence once. For each group, its first matching member remains the representative and members retain sorted order. Build the final sequence by ordering group headers and ungrouped cards only when required: a flat ungrouped catalog must reuse the first sorted sequence instead of sorting it again. Preserve the final group-name/column comparison semantics and kind/ID tie order; simply replacing a group at its first member position is not sufficient for title sorting.

Alternative: only replace localeCompare. The experiment proves its value, but it leaves view-triggered recomputation and duplicated work. Server sorting or a Web Worker introduces new contracts/copying costs before the existing synchronous model has been corrected.

### Depend on effective model inputs

Use explicit primitive values or a stable semantic key for q/markets/tags/stock/deals/participationFirst/sort rather than full URLSearchParams identity. Exclude view, performance fixture parameters and other unrelated URL state. Snapshot preparation and projection have separate memo boundaries; tag/market selections keep their accepted empty/default meaning. Replace superseded helpers and update their consumers/tests rather than keeping duplicate pipelines.

Alternative: debounce all filters. It changes interaction timing and leaves unnecessary calculations, so retain React's existing deferred rendering model.

### Keep urgent input separate from deferred results

Use a coherent deferred catalog navigation context for results and stable sort/edit callbacks. Input and URL remain current immediately; result links carry the query corresponding to the rendered results and settle to the latest query. Preserve reset/view races already guarded by synchronous navigation. Do not remove flushSync indiscriminately. Tests cover rapid typing, reset followed by another filter, details/back context, and an immediate card click while results settle.

Alternative: memo every value or add a second search store. Stable existing boundaries are sufficient and avoid synchronization complexity.

### Subscribe to collection state at the smallest boundary

Extend the existing split collection contexts with a memoized action/status value containing commands and the derived collecting lock (and existing start error), excluding progress counters. AppShell consumes that value; ActiveCollectionPanel retains the full progress subscription. Update affected consumers/tests completely. Progress-only updates must leave unchanged filters/forms/results untouched, while start, waiting, terminal and error transitions remain observable. Keep form mount/focus behavior; do not conditionally unmount drawers as a performance shortcut.

Alternative: memoize only CatalogFilters. This leaves full shell/form rendering, unstable callbacks and tag preparation. A new external state store is disproportionate. This is a local refinement of the existing provider split, not a significant application architecture change; no ADR is required.

### Measure varied release data and assert meaningful boundaries

Repair benchmark labels to match current UI and disambiguate global/group actions. Preserve existing deterministic fixture cases used by E2E; add an opt-in seeded varied dataset in mock-only code with decimal/null prices, numeric/case/Cyrillic titles, all marketplaces, tags and availability. Use the same seed, data and browser before/after. Benchmark all seven sort columns in both directions, search with active title sorting, selection, list/grid, group search/selection, and progress-only updates across 100/1000/5000 plain/mixed/group data. Use 5 warmups and 30 samples per measured action; record environment, browser version, p50/p95, DOM and available heap/long-task evidence. Missing memory is recorded as unavailable.

Capture an unoptimized baseline from HEAD before model changes, using the repaired harness and identical mock-only fixture in isolated temporary sources/builds outside user data. Add machine-readable per-action threshold results and fail the benchmark command on violated budgets. Use existing <=200 ms threshold, or at least 30% improvement when that action's matched baseline exceeds 200 ms. Retain baseline-regression visibility even where the conditional improvement rule passes.

Use semantic tests for sorting/group representatives and hook/render-count tests for view-only model reuse, urgent-input isolation, and sidebar/form isolation. Existing DOM mutation assertions alone cannot detect wasted renders; extend rather than substitute them. Keep timing checks in the release benchmark, not wall-clock unit tests. Temporary assets/reports stay outside the repo unless a small durable verification summary is needed in the workflow record.

## Risks / Trade-offs

- Group header ordering differs from member ordering → compare existing and optimized semantics for every column/direction, ties, nulls, filters and counts.
- Deferred results could carry stale navigation → verify immediate and settled links plus details/back in E2E.
- Stable status context could miss lock/error transitions → test queued/running/waiting/terminal states and start errors separately from counter updates.
- Timing is machine-dependent → matched release runs on an idle host, fixed seed/viewport, warmups, full distributions and explicit failures; do not loosen budgets to hide regressions.
- Excess memoization can hide updates → test changed snapshots, group edits, filters and collection completion, not only unchanged input reuse.

## Migration Plan

No persisted migration or compatibility layer. Replace affected frontend internals and migrate their consumers/tests in the same implementation. Shared live/mock catalog UI uses the new path; fixtures remain absent from desktop release assets. API, worker, queued collection, `main.py collect` and numeric database-free Ozon mode retain their contracts because backend code is untouched. Validate via frontend lint/unit/E2E, release benchmarks and desktop build; report native runtime smoke availability separately. On acceptance sync this delta, archive the change and commit closure documentation. Do not retain an old implementation as a fallback.

## User-approved participation refinement

During evaluation the user requested a second option in the deal filter that selects dealsEnabled products regardless of whether they are currently profitable, and a checkbox immediately after Availability. The user confirmed explicit labels: «Участвуют в выгодных предложениях» and «Сначала товары, участвующие в выгодных предложениях».

Use `deals=participating` for filtering. Existing all/deals/non_deals meanings remain. The checkbox is on by default; `participationFirst=0` opts out. Its ordering prefix applies before the selected column comparator, to cards, group representatives and members. With the checkbox on, unknown prices are last within each participation block; with it off, existing exact column/null ordering spans all products. Default sort is participation then descending exact savings, followed by availability/price and stable kind/ID ties; actual deal eligibility is not an extra earlier rank. Without the checkbox prefix default sorting is savings-first. Reset restores the checked default and retains view; URL, reload and details navigation preserve both new settings. Include both settings in the semantic model key.

This explicitly requested evaluation revision supersedes the earlier participation/availability/default-priority order and unconditional cross-participation column ordering. Backend/API representatives, persisted dealsEnabled flags, migrations and collection behavior are unchanged. Verify contradictory inputs: disabled high-savings product versus enabled nondeal, profitable versus participating filter, every column with prefix off, group membership/representative and zero/null savings.
