# Proposal

> Revised after the user's decision to retain browser E2E as the main UI test suite. Implementation still requires explicit plan approval under `$vibe-flow`.

## Why

The project has three dependency managers, but the frontend manifest uses `latest` and Python requirements allow broad upgrades. A normal Vite web path still exists alongside the supported Tauri desktop application. Cleanup needs an auditable dependency policy, measured build and runtime baselines, and explicit preservation of desktop, CLI, and JSON behavior.

## What Changes

- **BREAKING** Remove the standalone live web UI path (`npm run dev`, plain web build/preview, Vite API proxy, browser-relative live API fallback, and web-only CORS origins). Keep the FastAPI server required by desktop and CLI.
- Preserve the browser E2E fixture (`dev:e2e`, mock API, Playwright tests) as the main UI test suite. Tauri E2E is a separate future change; it is not part of this cleanup.
- Audit direct and transitive Python, Rust, and frontend dependencies. Remove only dependencies proven unused after checking runtime, tests, packaging, and platform paths.
- Replace frontend `latest` and broad Python direct ranges with a documented compatibility and reproducible-install policy: exact frontend direct versions with `npm ci`, Cargo.lock with `--locked`, and a hashed, transitive Python `requirements.txt` compiled from reviewed direct requirements. Account for AUR's system-managed Python dependencies.
- Compare the sizes of frontend assets, the desktop binary, and the release archive before and after dependency cleanup using the same build procedure. Do not include speculative runtime optimization; if a concrete slowdown is found, profile that execution path before proposing a change.
- Check tests and the desktop execution path after each implementation stage, and update the affected run, packaging, and architecture guides.

## Capabilities

### New Capabilities

- `desktop-runtime-delivery`: The live UI is built and connected for Tauri desktop; the browser E2E fixture remains for automated UI tests.
- `reproducible-dependency-installation`: Supported install and build paths select reviewed dependency versions consistently across Python, npm, and Cargo.

### Modified Capabilities

None; the repository has no main OpenSpec capabilities yet.

## Impact

Affected areas: `frontend/package.json` and lockfile, Vite configuration, React API bootstrap, `requirements.txt` and Python install/release paths, `Cargo.toml` and lockfile, API CORS configuration, packaging scripts, and focused documentation. Existing migrations and price history are not changed. Users of the old Vite + live FastAPI UI lose that path; desktop, browser E2E, API, worker, standalone CLI, and database-free numeric Ozon JSON mode remain supported.
