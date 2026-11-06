# Permanent catalog sidebar

## Authorization and plan

2026-11-06: User approved the iterated demo and explicitly requested «ПРиступай к переносу». This authorizes implementing the documented production-transfer checklist, not enabling the mock shell. Using vibe-flow and OpenSpec adopt-catalog-sidebar. No new product scope beyond the approved demo and real runtime wiring. Production transfer plan is captured in proposal/design/tasks and the existing checklist; implementation is authorized by this request. User evaluation remains required after implementation and commit.

The shell owns global add/group/import/refresh and real desktop tools; catalog filtering is permanent and single-model. Filters on details retain the saved catalog context and take the user to matching results when changed. No database/schema/API/worker/CLI change. Preserve unrelated whole-ruble-display.md edits.

## Verification plan

Typecheck, unit tests, mock E2E, desktop production build and list/grid visual checks. Browser plugin not available; use existing Playwright. Mock checks do not validate live services or native WebView. Repowise MCP index is 12 days stale at 9f3876d9; use current source and tests for critical claims. CodeGraph current source was read for shell/settings/catalog/filter paths.

## State

Implemented and verified; committing for user evaluation. Acceptance, spec sync and archive pending.

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

Preview server is running at http://127.0.0.1:5176/cards (normal mock catalog) or /cards?fixture=catalog (expanded test fixture). Both use the permanent UI. No live API/database/worker or native WebView/Chrome/OS registration was launched. Scope is frontend only, no migration. Preserve the unrelated `docs/workflow-runs/whole-ruble-display.md` working-tree edit. Commit all task changes before evaluation; do not push, sync or archive pending user acceptance.
