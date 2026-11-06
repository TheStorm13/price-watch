# Accepted implementation verification

Implementation of PERF-02/03/04/05 and related UI work, excluding Ozon transport,
rate or concurrency changes. Revised plan authorized by «Дейсвуй» on 2026-10-30.
User accepted the implementation on 2026-10-30 with «да» after the verification
summary. Relevant guides/backlog and five main specs are updated; the change is
archived at `2026-10-30-improve-ui-and-data-performance`.

## Behavior and data effects

- Collection commands have a separate stable context from progress. Catalog model,
  rows, tiles and groups are memoized. List/grid/group members and group candidates
  use measured virtualization. Selection stores all IDs independently of rendered
  rows. Focus owners and neighboring rows remain mounted for keyboard and menus;
  return navigation restores measurements/position for at most five contexts.
- Group filtering is deferred; selected membership uses a Set. Fixed Intl formatters
  are reused; chart preparation is memoized and exact Decimal extrema use one pass.
  SQL history/chart reads project domain fields without raw snapshot JSON.
- No diagnostic table. Only the latest CREATED run (maximum ID), including queued
  and retry runs, keeps at most 20 examples and 128 KiB. Messages/traces are bounded.
  Creating a run atomically expires all preceding diagnostics, including active
  ones. Rollback preserves the previous sample; late results cannot restore it.
  Exact counters, target results and retry scope are independent of the sample.
  Compact reads omit the errors column. API/UI expose complete/limited/expired.
- One log file per service, at most 10 MiB, no archives. Fresh process creation
  truncates it, and reaching capacity truncates the same file. Failure leaves the
  last file until another launch. Fixed chunks and one drain owner avoid line-sized
  buffers, queues and writes to deleted rotated files. Pipe shutdown is bounded.
- Export remains JSON v2 from one repeatable-read snapshot. It selects only exported
  history columns and indexes membership once. Decimal/order/group semantics remain.

Alembic 0017 intentionally deletes preceding diagnostic details and limits the last
sample, as authorized; price history/cards/targets/counters are preserved. Upgrade
must run with collection writers stopped and owned active runs already finished or
recovered by the old worker. The migration refuses owned running/waiting runs rather
than partially changing them. No user database was migrated during development.
There are no compatibility adapters or second writer implementations.

## Reproduction and measurement limits

Baseline source: worktree at `799064b`; after: this implementation. Private database
`price_watch_rel_test` in `/tmp/pw-performance-pg`, port 55479, private `perf_*` schemas.
No user database, XDG directory or marketplace profile was used.

Browser: release mock fixture, Chromium, 1440×1000, ru-RU. Use
`VITE_E2E_TEST_MODE=true vite build --outDir <temporary directory>`, serve on loopback,
then `node scripts/benchmark_ui.mjs <loopback URL> <output.json>`.
Fixture only exists in E2E builds; the desktop build removes it. Five warmups and
30 measurements per action/case; wall time includes Playwright and two animation
frames, not pure CPU time. Baseline's first eight cases were collected across an
interrupted session and partly overlapped verification, so precise speedup ratios
are indicative; raw samples are retained. After cases ran sequentially after heavy
checks. Earlier baseline cases lack heap/long-task fields, which were added later;
missing memory is not presented as measured. Browser results are not native p95.

`scripts/benchmark_diagnostics_export.py --source-root <source> --schema perf_<name>
--case export|errors|history --size <count>` uses only the named disposable database
and its private schema. Each export runs in a fresh process; peak RSS includes
fixture/client runtime. Export fixtures contain 100 history points/card with 1 KiB
snapshot bodies. Fixed timestamps make canonical JSON hashes comparable. Error
measurements use 0/20/100/1000/5000 failures and include exact counters/read latency.
History uses 10,000 observations, including availability gaps. Catalog uses existing
`scripts/benchmark_catalog.py`, ASGI HTTP serialization, 5 warmups + 30 samples,
100/1000/5000 cards ×100 observations and idle/concurrent writer cases.

`scripts/benchmark_process_log.py` streams 512 MiB of synthetic output into the real
Python drain: one file 2,097,155 bytes, parent RSS 18,848→19,084 KiB, 4 descriptors and
one thread both before and after. Rust/Python tests separately cover stdout/stderr,
capacity, fresh start, retained tail, inherited open descriptors and synthetic
`/dev/full` I/O failure. This failure is deliberate, not an actual full disk.

## Release UI results

All nine cases pass p95 ≤200 ms. Every action whose baseline exceeded 200 ms improves
by at least 30%. The rendered DOM is identical between 1000 and 5000 cards for each
shape (480 plain/mixed, 505 one large group), within the 20% threshold. No pageerror
or console error was captured. Render instrumentation/E2E verify 30 progress updates
leave unchanged catalog DOM untouched. All IDs remain in the in-memory snapshot.

| 5000 cards | DOM before → after | selection p95 | search p95 | sort p95 | grid/list p95 | group search/selection p95 |
| --- | --- | --- | --- | --- | --- | --- |
| Plain | 135153 → 480 | 82.1 ms | 48.7 ms | 98.8 ms | 115.1 / 99.1 ms | 81.1 / 163.4 ms |
| Mixed groups | 149653 → 480 | 82.3 ms | 48.8 ms | 98.3 ms | 99.1 / 99.0 ms | 81.6 / 161.3 ms |
| One group | 135182 → 505 | 82.4 ms | 48.7 ms | 82.4 ms | 115.0 / 99.0 ms | 77.8 / 149.8 ms |

Raw [before](ui-before.json) / [after](ui-after.json) include all sizes/actions.
The highest p95 over all after cases is 198.4 ms (100-card group selection).

## Diagnostics and export

At 5000 failures stored examples shrink 5000→20, JSONB text 3,397,786→13,502 bytes;
failure_count remains 5000. Last-quarter mean write time 18.85→2.01 ms; compact
read p95 26.78→1.79 ms. Small-run writes have an extra guard/bounded-update cost
(20 failures total 28.8→52.2 ms); bounded storage and flat large-run cost are the
intended benefit. Full numbers: [resource measurements](backend-resources.json).

| Export cards / observations | Time before → after | peak RSS before → after |
| --- | --- | --- |
| 100 / 10000 | 0.145 → 0.058 s | 114736 → 82772 KiB |
| 1000 / 100000 | 1.318 → 0.606 s | 486960 → 153308 KiB |
| 5000 / 500000 | 8.247 → 3.353 s | 2130292 → 454080 KiB |

Large export passes RSS ≤0.75× (0.213×) and time ≤1.10× (0.407×). Canonical SHA256
matches for every size. Controlled integration writes change title/history/group
between export queries and prove the old snapshot stays coherent; the next export
sees all committed changes. Existing import roundtrip/order/Decimal checks pass.

## Verification status

| Check | Result |
| --- | --- |
| Full Python with disposable PostgreSQL | 219 passed; subsequent current diagnostics/migration 9 passed, current reliability/diagnostics 23 passed, concurrent-export test passed |
| Frontend unit | 75 passed; final extended diagnostics panel file 4 passed (one new case) |
| Full browser E2E | 58 passed, including first/last/resize, Tab/overlay, hidden membership and scroll return |
| Frontend lint/typecheck | Passed |
| Rust default suite | 11 passed, 3 ignored by default |
| All three opt-in native Rust tests | 3 passed separately in private directories, including real Chrome closure and API/Xvfb/PostgreSQL recovery |
| Desktop release build | Passed; four built JS assets contain no performance fixture markers |
| Native WebView, real API/worker/private DB | Retry + price 100.10 + API restart passed; 5000-card search/last card/grid passed, initial accessible card checkboxes 11 |
| CLI without DATABASE_URL | 6 tests, OK with 1 skip; collect help/import paths passed |
| OpenSpec strict validation / diff whitespace | Passed |

[Native smoke](native-smoke.json), [native screenshot](native-large-catalog.png),
[log resources](process-log-resources.json). Actual native service log files measured
767/936/543/0 bytes, no archives; stress tests exercise the configured limits.
The extended native harness was corrected after fixture/API assumptions failed:
synthetic unsupported marketplace was replaced with known non-collectible cards;
WebKit lacks EditableText and its container role differs from Chromium. Private
Xvfb/XTest input and checked radio state now verify the real interaction. Earlier
failed harness attempts are not counted as passed tests. AT-SPI API reference:
[GNOME keyboard synthesis](https://docs.gtk.org/atspi2/func.generate_keyboard_event.html)
(Context7 only offered a different Rust binding, so official docs were used).

Native results are functional smoke, **not native p95 measurements**. Browser p95
and heap observations must not be presented as Tauri latency or process RSS.
Mock/performance fixtures do not test real marketplace responses. Real Ozon network
collection/speed was outside this change. Backend and native tests use isolated
services/data; user DB and profiles remain untouched.

[History benchmark](history-resources.json): 10,000 points, p95 123.77→66.35 ms,
peak RSS 119508→90908 KiB, equal output hashes including availability gaps. Chart
unit checks cover exact Decimal extrema beyond floating-point precision and a
150,000-point domain without a spread-call argument limit.

Catalog [first before](catalog-before.json)/[first after](catalog-after.json) retains
the initial L_writer outlier (766.36→1039.66 ms), which failed its p95 budget.
The final L-only pair ran sequentially with no concurrent build/test/benchmark:
[isolated before](catalog-before-isolated.json)/[isolated after](catalog-after-isolated.json).
L idle p95 603.17→681.15 ms (≤723.81 target), writer p95 767.34→696.65 ms
(≤920.81 target), writer throughput 159.87→159.24 cards/s (≥127.89 target).
RSS 155582464→154443776 idle /179535872→177860608 writer bytes. SQL count3.
S/M pass in the full pair; isolated L passes all p95/RSS/throughput/SQL criteria.
An intermediate repeated pair overlapped E2E because a coordinator process matcher
used an absolute rather than actual relative Python argv; it is not used as the
isolated acceptance measurement.

Repowise change risk reads the live diff at HEAD 799064b but its graph/history index
still advertises old 9f3876d9ba3f. Test selection is therefore bounded by full suites
and current-source review, not its stale coverage graph. Structural warnings
(complexity 29 in CatalogResults and nested row/candidate rendering) were reviewed:
they describe rendering branches, not demonstrated defects. E2E specifically covers
large groups, first/last cards, resizing, focus/Tab/overlay ownership, scrolling,
selection, hidden membership and return navigation.

The local `repowise update --working-tree` completed after measurements, but MCP
still returns its old indexed commit. Its live-diff warnings were reviewed against
current source. Reaper diagnostic append now runs only for non-expired records
(at most one under the latest-only invariant), so it does not issue a diagnostic
query for each preceding stale run. The Rust optional file unwrap follows a checked
initialization branch in the same exclusive owner and cannot observe a missing file
there. Complexity warnings remain maintainability observations, covered by focused
functional tests; no automatic score is treated as runtime proof.

## Documentation and closure

The [API/data guide](../../guide/DATA_AND_API.md),
[architecture](../../guide/ARCHITECTURE.md), [UI specification](../../UI_SPECIFICATION.md)
and [testing guide](../../guide/TESTING_AND_TROUBLESHOOTING.md) now describe the
accepted diagnostics/log policy, virtualization and reproduction commands.
Export JSON v2 and snapshot semantics are retained. PERF-02–05 and ARCH-02 are
removed from backlog; Ozon acceleration and the other architecture tasks remain.
[ADR 0010](../../adr/0010-bounded-ui-diagnostics-and-logs.md) is Accepted.
Five main specs were merged with unrelated requirements/Purpose preserved;
23/23 tasks are complete, and the change is archived after explicit acceptance.
Final task commit includes implementation, tests, evidence and documentation.
