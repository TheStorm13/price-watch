# Tasks

## 1. Baselines and approval

- [x] 1.1 Run isolated development mock UI diagnostic for 100/1000/5000 cards; record raw observations, DOM counts, methodology and limitations in workflow record. Verify no application code or user data changed.
- [x] 1.2 Reconcile acceptance after the 2026-10-30 retention correction; record that the earlier yes was followed by a pause and a narrower diagnostics/log policy. Confirm the revised concrete plan before application implementation; do not treat approval of the superseded table/archive design as current.
- [x] 1.3 Add reproducible release UI benchmark fixtures/harness and run 5 warmups + 30 samples for list/grid/group/editor interactions; capture viewport, versions, console, DOM, timing and memory. Verify fixture never reads user data and retain before results.
- [x] 1.4 Prepare disposable TEST_DATABASE_URL and run before catalog/error/export measurements as described in design; verify separate database identity and retain baseline artifacts. No existing user database may be reused.

## 2. Catalog and collection UI: PERF-02 and related ARCH-02

- [x] 2.1 Separate stable collection commands/start state from progress subscriptions and fix mutation dependency identities; verify with unit render instrumentation that 30 progress changes do not commit unchanged catalog results while terminal refresh/notifications still work.
- [x] 2.2 Extract catalog view model and memoized row/tile/group components with stable callbacks and selection; verify existing filtering/sorting/group/selection unit and E2E behavior, including partial failures.
- [x] 2.3 Install only the chosen virtualizer with pinned version/lockfile; virtualize list rows and responsive grid rows including large-group members. Verify bounded DOM and first/last cards for 1000/5000 results and one group of 5000.
- [x] 2.4 Preserve table semantics, keyboard focus, overlay ownership and return scroll position; verify E2E across offscreen selection, resize, sort/filter changes, action menus, detail/back and empty/error states.
- [x] 2.5 Repeat release UI benchmarks against 1.3 and document per-case thresholds; verify p95, render isolation and bounded DOM before marking PERF-02 addressed. Prepare relevant UI guide draft; publish after acceptance.

## 3. Group editor and price details

- [x] 3.1 Use a selected-ID Set, memoized/deferred filtering and bounded candidates in GroupDialog; verify 4000 selected among 5000 cards, search/sort/scroll/last candidate, keyboard and unchanged full saved membership with unit/E2E and release timing.
- [x] 3.2 Reuse fixed Intl date/relative formatters without caching stale formatted output; verify existing date behavior and relevant frontend tests.
- [x] 3.3 Memoize chart preparation and renderer, replace extrema sorts with exact single-pass comparisons, and select only needed history/chart SQL columns; verify Decimal extrema, unavailable gaps, all points, pagination, unit and PostgreSQL tests and long-history timing. Prepare relevant guide draft if observable behavior needs clarification.

## 4. Run diagnostics: PERF-03

- [x] 4.1 Keep the existing errors field; add diagnosticsStatus and atomic Alembic 0017 normalization to examples of only the latest-created run (maximum ID), regardless of status. Verify ≤20 entries/128 KiB, intentional expiry of every earlier run including active runs, unchanged runs/counters/targets/prices/history, migration rollback and historical revision tests on disposable DB. Do not create an errors table.
- [x] 4.2 Bound all error writers and reserve space for a terminal general error; stop changing diagnostic payload once limits apply. Preserve lease, pending-target transition and exact counters independently of retained examples. Verify duplicate delivery, oversized Unicode errors, stale recovery, creation-time cleanup including queued/retry, creation rollback and concurrent late-writer/finish tests.
- [x] 4.3 Carry include_errors through API/ports/read adapter without loading error payload for compact reads/heartbeat. Carry complete/limited/expired status through domain/API/mock/UI; verify explanatory UI, sampled traceback bounds, unchanged retry scope and full failure counts.
- [x] 4.4 Repeat 0/20/100/1000/5000-failure benchmarks and document payload/write/read limits and progress p95; verify bounded storage despite many runs, only latest-created-run diagnostics and no user DB access. Prepare retention/architecture/API documentation draft.

## 5. Process logs: PERF-04

- [x] 5.1 Implement one bounded Rust process log owner with fixed-size pipe reads and serialized stdout/stderr writes; wire API/PostgreSQL/Xvfb/worker/manual Chrome and lifecycle writes. Verify one file, truncation at capacity and before restart, I/O errors and bounded shutdown without unbounded queue or deleted-inode writes.
- [x] 5.2 Implement the same single-file policy in shared Python ChromeSession for queued/direct/numeric collection; verify session/profile tests, long-line/continuous output, fd/thread cleanup and bounded shutdown without DATABASE_URL. Do not change Ozon transport/rate/concurrency.
- [x] 5.3 Verify isolated native services keep one file ≤10 MiB each with no archives; last output remains after failure until the next start. Retain disk/RSS/recovery evidence and prepare troubleshooting/retention documentation draft.

## 6. Export: PERF-05

- [x] 6.1 Project only exported history columns and pre-index group membership, retaining one consistent snapshot and JSON v2; verify canonical before/after output, Decimal/order/groups, import roundtrip and concurrent-writer integration tests.
- [x] 6.2 Repeat large export timing/RSS benchmark with realistic snapshot payloads; verify RSS≤0.75×baseline and time≤1.10×baseline or surface unmet criteria for a revised plan. Do not silently introduce streaming HTTP/Tauri contract. Prepare export documentation draft if needed.

## 7. Integration and human acceptance

- [x] 7.1 Run relevant full Python, frontend unit/E2E/lint, Rust tests and desktop build; inspect diff and current contracts. Verify queued API/worker, direct collect and numeric CLI imports without DATABASE_URL and report any unrun checks explicitly.
- [x] 7.2 Run isolated native WebView smoke and release UI benchmark comparison, review migrations/data/resource effects and update workflow verification. Present implementation for explicit user acceptance before closing tasks or changing backlog status.

## Workflow follow-up

- After explicit acceptance, publish only relevant documentation drafts, update the accepted ADR status, remove completed backlog entries, sync specs and archive the change.
- Inspect staged diff, create task commits including tests/documentation/OpenSpec and verify hashes. Do not push or merge.
