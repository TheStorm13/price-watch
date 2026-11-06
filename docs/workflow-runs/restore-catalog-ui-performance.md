# Restore catalog UI performance

## Status

2026-11-06: planning prepared; explicit approval of the concrete plan is pending. Application code, tests and harness are unchanged. User requested `$vibe-flow`, a plan covering all findings, and implementation. The selected skill requires approval after presentation of that plan before code edits; implementation will begin on that approval, followed by a separate acceptance gate.

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

Present the plan and request explicit approval under vibe-flow. After approval, use openspec-apply-change, read this record, assess affected current files/tests and implement tasks in dependency order. After implementation and commits, request acceptance; sync/archive only after acceptance.
