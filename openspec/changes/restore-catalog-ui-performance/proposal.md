# Proposal

## Why

The accepted sidebar redesign introduced expensive locale-aware sorting and unnecessary model/component updates. Investigation on 2026-11-06 reproduced approximately 217 ms median title-sort and 205 ms search latency on 5000 randomized-name products in a release mock; replacing only locale comparisons reduced these to 87/60 ms, while virtualization remained bounded.

## What Changes

- Reuse a Russian numeric collator, prepare the comparator once per sort, and remove redundant sorting without changing member-based filtering or representative selection.
- Separate snapshot-derived preparation from filter/sort projection; exclude presentation-only URL parameters from model dependencies and reuse tag preparation.
- Restore deferred result navigation context and stable results callbacks so typing does not synchronously rerender unchanged product rows.
- Isolate collection progress subscriptions from sidebar filters and closed forms; preserve immediate collection locks, errors and terminal snapshot invalidation.
- Repair the existing benchmark selectors and add seeded heterogeneous data, all column sorts, timing budgets and render-isolation coverage.

- User review refinement: add the participating-products filter, a default-on participation-first checkbox, and participation then savings default ordering; explicit column sorts honor the checkbox.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `catalog-sidebar`: participating-products option and participation-first control, with URL/reset behavior.
- `group-card-metrics`: shared participation/savings ordering and member-level participation filtering.
- `catalog-snapshot`: extend existing responsiveness verification to heterogeneous data and require progress-only isolation for unchanged sidebar filters/forms as well as catalog rows.

## Impact

Frontend catalog model/hooks/results, sidebar shell, collection context boundary, mock-only performance fixtures, frontend tests, `scripts/benchmark_ui.mjs`, and the performance testing guide. No new dependency, backend contract, Tauri command, migration or persisted data change. Desktop UI and mock UI share the optimized implementation; API, worker, collection CLI and database-free numeric Ozon mode are unaffected.

Acceptance: preserve catalog semantics and layout except the explicitly requested participation/filter ordering refinement; keep virtualized DOM bounded; unchanged filters/forms/results do not render on progress-only updates; view-only changes do not recompute the catalog projection. Release before/after measurements use identical seeded 100/1000/5000-card plain/mixed/group datasets, 5 warmups and 30 samples, reporting p50/p95, DOM, memory and environment. Existing p95 <=200 ms / >=30% improvement when baseline exceeds 200 ms applies per measured action; failures remain blockers and are reported explicitly.

Main risks: changing group tie order/representatives, stale return context during rapid typing and navigation, stale collection locks, lost drawer focus/form state, and noisy performance measurements. Cover these with semantic tests, render-count tests, mock E2E and paired release benchmarks; native runtime evidence is reported separately.
