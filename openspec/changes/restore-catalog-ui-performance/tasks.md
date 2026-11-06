# Tasks

## 1. Reproducible baseline and benchmark

- [ ] 1.1 Repair `scripts/benchmark_ui.mjs` search/action selectors and add opt-in seeded heterogeneous data in the mock-only performance fixture, preserving current fixtures; verify existing performance E2E and fixture determinism for 100/1000/5000 plain/mixed/group catalogs.
- [ ] 1.2 Add both directions of all seven column sorts, active-sort search, existing selection/view/group interactions and progress observation to the harness; implement per-action baseline comparison and failing exit status, verified with passing/failing synthetic benchmark-result inputs.
- [ ] 1.3 Document exact release build/serve/benchmark commands and timing/budget interpretation in the testing guide; execute the repaired harness against isolated unoptimized HEAD sources with the same fixture and save baseline/environment outside the repo before runtime changes.

## 2. Catalog preparation and sorting

- [ ] 2.1 Prepare collator and comparator outside sort loops; preserve exact decimals, nulls, availability and ties, verified by catalog model tests covering all seven columns in both directions and numeric/Cyrillic/case names.
- [ ] 2.2 Separate snapshot preparation and filter/group projection, avoid the second sort for flat catalogs, and remove duplicate/unused tag work; verify combined member filters, representative/title ordering, deal/default order, counts, ties and snapshot immutability with focused tests.
- [ ] 2.3 Depend only on effective filter/sort values in `useCatalogModel`; verify view/unrelated-param changes retain model output identities while changed filters and changed snapshots produce current results using hook tests.

## 3. Urgent input and result rendering

- [ ] 3.1 Restore coherent deferred result return context and stable `onSort`/`onEditGroup` handlers in CardsPage; verify with controlled render tests that an urgent input update does not rerender unchanged product rows before deferred results change.
- [ ] 3.2 Add mock E2E for rapid typing/reset/filter changes, immediate versus settled result navigation, details/back context and group editing; verify selections, focus, counts and URL/header/sidebar synchronization remain correct.

## 4. Collection progress isolation

- [ ] 4.1 Refine the existing collection context split with stable command/derived-lock state and migrate AppShell and affected consumers; verify provider tests for queued/running/waiting/terminal states, start errors and completion invalidation.
- [ ] 4.2 Add meaningful sidebar/filter/form/result render-count tests for counter-only progress updates and retain existing DOM-mutation E2E; verify open-form input/focus preservation and immediate refresh/Chrome locks and service errors.

## 5. Integrated verification and review

- [ ] 5.1 Run frontend lint/typecheck, all unit and mock E2E tests, then desktop release build; inspect desktop assets for fixture leakage and report any unavailable native smoke explicitly. Verify no backend/API/worker/CLI/database change or migration entered the diff; PostgreSQL tests, if newly necessary, use only disposable TEST_DATABASE_URL.
- [ ] 5.2 Run matched release after benchmarks with 5 warmups/30 samples, 100/1000/5000 plain/mixed/group seeded data, both directions of all columns and active-sort search; report p50/p95, DOM/memory/environment and every budget result against baseline. Diagnose failures before requesting acceptance.
- [ ] 5.3 Verify rendered list/grid, sorting, filters, drawer focus and progress at 1440x900 and 1024x768; inspect screenshots/console and preserve bounded scrolling, last-item access and position restoration, with evidence outside the repo.
- [ ] 5.4 Review current diff/affected tests with Repowise (state index limitations), run strict OpenSpec and whitespace validation, update the workflow record with verification and risks, then create and verify task commits before requesting user acceptance.

## Workflow follow-up

- Wait for explicit approval of this plan before application/test/harness implementation.
- After implementation commits, wait for explicit user acceptance; commit any reviewed revisions before requesting evaluation again.
- After acceptance, sync the catalog-snapshot delta, archive this change, update the relevant workflow/testing documentation and commit closure changes. Do not push or merge without separate authorization.
