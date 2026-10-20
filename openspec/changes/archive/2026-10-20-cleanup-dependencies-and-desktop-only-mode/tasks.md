# Tasks

## 1. Baseline and audit

- [x] 1.1 Record toolchain versions, clean-install commands, frontend asset bytes, desktop binary bytes, and equivalent local archive bytes; verify the record contains matching commands and conditions for later size comparison.
- [x] 1.2 Map each direct Python, Rust, and frontend dependency to its runtime, test, build, or packaging consumer; verify removal candidates against desktop, worker, CLI, numeric Ozon JSON, and AUR paths and record a keep/remove decision for each.

## 2. Remove only the live web UI path

- [x] 2.1 Remove the plain live Vite scripts, API proxy, implicit browser-relative live API branch, and web-only CORS origins; retain `dev:e2e`, mock API, Playwright configuration and Tauri API. Verify static searches and focused frontend/API tests distinguish the two paths.
- [x] 2.2 Run TypeScript lint, Vitest, all browser E2E scenarios, and `desktop:build`; verify the built desktop can start and reach its local API with isolated test data, or report a concrete environment blocker without using the user database.
- [x] 2.3 Run API/CLI tests and check `main.py api`, direct `main.py collect`, worker queue, and numeric Ozon JSON import/execution paths; verify numeric mode remains independent of `DATABASE_URL` and both CLI imports work. Use only a disposable `TEST_DATABASE_URL` for PostgreSQL integration checks.

## 3. Frontend and Rust dependencies

- [x] 3.1 Pin reviewed direct frontend versions, remove verified unused packages while retaining Playwright E2E dependencies, regenerate `package-lock.json`, and verify a clean `npm ci`, lint, Vitest, browser E2E, desktop build/start, and asset-size measurement.
- [x] 3.2 Remove verified unused Rust crates/features, select compatible direct versions, regenerate `Cargo.lock`, and verify `cargo test --locked`, a locked desktop build/start, browser E2E, and binary-size measurement.

## 4. Python dependencies and reproducible installation

- [x] 4.1 Put verified Python direct requirements with tested compatible bounds in `requirements.in`, compile fully pinned hashed `requirements.txt` with a pinned pip-tools version for the supported Linux/Python target, and verify a clean `pip install --require-hashes -r requirements.txt`, `pip check`, and regenerated-lock consistency.
- [x] 4.2 Re-run Python unit/API/CLI tests, browser E2E, desktop build/start, worker, direct collection, and numeric JSON checks after the Python lock change; run PostgreSQL integration tests only with a disposable `TEST_DATABASE_URL` and report any unavailable live checks.
- [x] 4.3 Verify release staging includes the correct Python install inputs while the AUR recipe continues using system Python packages; inspect staged files and run packaging checks possible without changing user data.

## 5. Build-size outcome and review

- [x] 5.1 Repeat the same builds and report before/after asset, binary, and archive sizes; if a concrete runtime problem appears, choose a focused fix, measure that path before and after, and run relevant tests without adding a general profiling workflow.
- [x] 5.2 Review the final diff, all affected modes, API/auth contract, data effects, migrations, and outstanding checks; verify tests/lint/build results are recorded accurately and present the implementation for user acceptance.

## Workflow follow-up

- After implementation acceptance, update only affected run, test, architecture, dependency, and packaging documentation; verify every documented command and mark ADR 0002 accepted if the decision is confirmed.
- Sync the delta specs and archive the OpenSpec change after acceptance and documentation updates.
