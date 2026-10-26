# Tasks

## 1. Shared storefront session

- [x] 1.1 After explicit plan/ADR approval, replace per-product page creation/navigation with one owned storefront page and single-flight lazy/explicit session bootstrap; verify no product goto, bootstrap races, standalone, concurrent and repeated-session behavior.
- [x] 1.2 Preserve profile/region, challenge handlers and CDP closure; implement request-specific cancellation and one shared recovery after in-flight requests drain. Verify neighbor requests survive individual cancellation, concurrent access failures share one refresh, successes stay intact and whole-session cancellation closes resources. Draft relevant documentation changes for acceptance; publish them after the second vibe-flow gate.

## 2. Validated and bounded JSON requests

- [x] 2.1 Implement encoded product GET through in-page fetch with credentials include, abortable timeout and response metadata; verify browser-backed or mocked transport checks plus exact raw preservation and unchanged normalized fixture output.
- [x] 2.2 Add explicit HTTP/content/schema checks, bounded transient retries, Retry-After parsing/shared cooldown and at most one session refresh; verify 403 JSON, HTML, malformed JSON, 404 ambiguity, 429 numeric/date/invalid/long, 5xx, timeouts and cancellation without false ProductNotFound.
- [x] 2.3 Preserve default concurrency 5 for actual overlapping fetch calls, with an independent initial 5-starts/second limiter of burst capacity 5; verify five requests start before any completes, the sixth waits, retries obey the same limit, parallel 429 responses extend shared cooldown and waiting requests recheck it before dispatch. Update research/workflow evidence and documentation draft.

## 3. Cross-mode verification and review

- [x] 3.1 Run affected parser/mapper/Decimal/raw/connector/CLI/collection/profile suites and full Python suite, report actual pass/skip/failure counts; verify both CLI imports, numeric mode without DATABASE_URL and direct/queued consumers. Use only disposable TEST_DATABASE_URL if integration tests run.
- [x] 3.2 Repeat live requests with the authorized price-watch profile, including a batch with concurrency 5 and repeated-session requests; verify overlap/reuse/no per-product navigation and capture only sanitized field availability/timing/status evidence. Compare timing/navigation overhead against the old path at the same concurrency and report measurement limits.
- [x] 3.3 Review diff and change risk, check git diff --check and strict OpenSpec validation, present changed files/checks/remaining risks for explicit implementation acceptance.

## Workflow follow-up

- After explicit implementation acceptance, update the relevant README/guides, mark the ADR accepted, sync specs and archive the change.
- Stage only accepted task files, inspect staged diff, create Git commit(s), verify hashes and report them. Do not push or merge.
