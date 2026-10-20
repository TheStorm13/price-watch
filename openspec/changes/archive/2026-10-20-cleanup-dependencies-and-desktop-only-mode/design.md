# Design

## Context

See `proposal.md`. Tauri invokes `dev:desktop` and `build:desktop`; plain `dev`/`build` still provide a browser-relative live API path through Vite's proxy to port 8000. The separately named `dev:e2e` path uses mock API data for Playwright and does not exercise live services. FastAPI has browser-development and Tauri CORS origins. npm and Cargo lockfiles are committed; Python has only broad direct requirements. `packaging/make-linux-release.sh` runs `npm ci`, while AUR installs Python libraries as system packages. The working tree contains an in-progress background-desktop change; implementation must preserve those edits.

## Goals / Non-Goals

**Goals:** Establish one live UI delivery path, retain browser E2E for UI behavior, make dependency resolution reviewable, and assess build-size changes with matching build procedures.

**Non-Goals:** Replace the FastAPI service or CLI, change the database model or migration history, introduce Tauri E2E in this change, perform unrelated runtime performance optimization, or claim cross-platform reproducibility for a Python lock generated on one platform.

## Decisions

### Desktop-only live UI

Use Tauri as the sole **live** UI shell. Remove plain live Vite scripts, its API proxy and browser-relative live API fallback. Preserve `dev:e2e`, mock API, Playwright browser tests and their test-only browser server. Keep Tauri CORS origins and API routes; remove only origins exclusive to the old live Vite mode. Keep `main.py api` because Tauri launches it and the standalone CLI uses it. Continue browser E2E as the principal UI regression suite; use desktop build/start checks for runtime integration. Tauri E2E is a separate future change and need not duplicate all browser scenarios. Alternative: remove the browser E2E fixture with live web; rejected after user review because it loses useful fast UI coverage. Alternative: retain the live Vite path as undocumented development tooling; rejected because it leaves a second, unverified live connection path. See Proposed ADR 0002.

### Version and install policy

For npm, pin direct versions to reviewed exact versions, regenerate `package-lock.json`, and use `npm ci` for setup and release. For Rust, retain compatible direct crate requirements and commit `Cargo.lock`; use `cargo ... --locked` for verification/build, changing a crate only after checking its use and plugin compatibility. For Python, put reviewed, tested direct compatible bounds in `requirements.in`; generate a fully pinned, hashed `requirements.txt` with a pinned `pip-tools` maintainer version for supported Linux x86_64/Python 3.14. Clean local installation uses `pip install --require-hashes -r requirements.txt` and `pip check`. Record the compiler version and regeneration command. The AUR recipe continues to use distribution-managed Python packages; it does not use pip. Alternative: pin only direct Python requirements; rejected because transitive upgrades would still vary installations. The installed `pip lock` command reports itself experimental, so the plan uses pip-tools for this target.

### Dependency audit and build-size measurement

Map every direct dependency to imports, Tauri plugin registration, build/test tooling, or packaging. Confirm candidates by removing them in a clean install/build, not by static import search alone. Preserve runtime/dev distinctions and Linux system dependencies. Capture exact commands, toolchain versions, environment, and byte sizes for `frontend/dist`, the release desktop binary, and a locally staged archive; distinguish unpacked assets from compressed archive size. Compare before/after with the same command and platform. Build-size comparison is not a claim of runtime speed. If a concrete runtime slowdown is encountered during verification, measure that path separately before proposing any optimization.

## Risks / Trade-offs

- [Background-desktop edits overlap frontend and Rust files] → Start from the current tree, inspect each overlapping diff, and avoid reverting unrelated changes. Revalidate if that change moves before implementation.
- [Python hashed lock is platform and interpreter scoped] → State the supported target and regenerate/test separately when adding another target; AUR remains system-managed.
- [Removing the live-web branch may break the browser E2E fixture] → Keep the test flag and mock API explicit; run all 22 Playwright scenarios after each affected stage.
- [Tauri plugin versions may have coupled compatibility] → Change one verified dependency set at a time, regenerate the lockfile with Cargo, and run Rust tests and a desktop build.
- [Release script requires a clean Git tree] → Measure the equivalent local staged archive during implementation; run the release script only in a clean isolated checkout if needed.
- [No disposable PostgreSQL URL is configured] → Do not run integration tests against application data; report the missing check or create an isolated test database if available.

## Migration Plan

1. Record baseline build sizes and installation inputs. Audit dependency use and decide removal candidates.
2. Remove only the live browser UI wiring while preserving the browser E2E fixture and desktop API. Verify browser E2E, desktop build/start, and standalone CLI/API/JSON paths.
3. Apply dependency pins and locks one ecosystem at a time; reinstall cleanly and run relevant checks plus desktop smoke after each stage.
4. Compare build sizes. If verification reveals a concrete performance problem, profile it and propose a separate, measured optimization before changing runtime behavior.
5. Update affected setup, architecture, test, and packaging docs after implementation acceptance. No data migration is required. Rollback is a source revision plus lockfiles; existing database and price history remain untouched.
