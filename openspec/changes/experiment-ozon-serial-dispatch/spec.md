# Task: Ozon serial dispatch experiment

## Goal and acceptance criteria

Compare Ozon A (5 concurrent requests, 5 starts/s), B (1, 5/s), C (1,
no planned start limit) on the same fixed 30–50 unique SKUs including variants.
Run A/B/C then C/B/A with pauses; retain async I/O, Retry-After, bounded retries,
timeouts and recovery. No user database access or history writes. No changes to
AliExpress, WB or default production collection policy.

Acceptance: reproducible JSON metrics for elapsed time, successful SKU/min,
queue/request times, actual composer dispatches, retries, 429, recovery,
errors and field completeness. Synthetic checks establish concurrency, pacing,
cooldown, cancellation and stop behavior before live runs. Live CAPTCHA or
repeated access refusal stops the experiment, preserving partial evidence.
Results must distinguish synthetic evidence, live evidence and inconclusive runs.

## Current system and evidence

`marketplace_connector/connectors/ozon/json_transport.py`: token bucket with
burst=concurrency, shared cooldown, max_attempts=3 and one recovery generation.
`async_client.py`: one storefront page per session, optional aspect-modal fetches.
`price_watch/application/collection_service.py`: five concurrent card attempts.
`marketplace_connector/application/retry.py`: one additional application retry.
`experiments/parallel_ozon.py`: existing DB-free two-mode experiment, no pacing
comparison or request instrumentation. `docs/tasks/ozon-session-json-transport.md`
records five historical live SKU seeds; availability today is unverified.
Backlog separately proposes measuring collection performance; it is unchanged.
CodeGraph returned current source. Repowise MCP targets obsolete 9f3876d despite
explicit repo path; its risk output is not used as current evidence. Local CLI index refresh is used instead; docs_enabled=false (deterministic pages only).

## Agreed solution

User approved the three-mode experiment on 2026-11-08 ("Да"), after selecting
Ozon only. Retain all failure handling; remove only planned pacing in C.
Support starts_per_second=None in Ozon client/transport, preserving positive finite
validation for numeric limits. None bypasses token accounting, not cooldown or
concurrency. Production callers keep default 5/s. This parameter is local policy,
not a claim about Ozon's published limits. No architectural boundary changes/ADR.

Replace existing experiment with instrumented real transport/client use. Instrument
only the experiment via a transport subclass/factory; do not store response bodies,
cookies, tokens, addresses or exception strings that could contain them. Capture
per-target logical attempts and per-dispatch queue/network timings separately;
composer counts exclude navigation/background browser traffic and are labelled.
Use the shared application retry policy and five logical card workers in all modes.
Count modal calls separately from card retries. Fresh transport per batch, same
browser session/profile across batches, equal pauses (default 30s), no cache-busting.
Report order/cache/session bias and six-run sample limitations.

Accept explicit SKU list or discover up to 40 from historical seeds and returned
variants before freezing the list. If fewer than 30 can be found, stop and report
instead of silently using a smaller comparison. User explicitly corrected profile
policy on 2026-11-08: use the existing stable Price Watch Chrome profile, not a new
temporary profile. Default follows XDG_DATA_HOME, normally
~/.local/share/price-watch/chrome-profile; reject missing profile directories.
Before launching, check that no other Chrome/collector owns it. Do not reset or
export cookies/session data. Synthetic tests use fake pages and require neither
Chrome nor network nor DB. Network/CAPTCHA blockers require a user decision.

Update docs/guide/TESTING_AND_TROUBLESHOOTING.md with experiment commands,
metric definitions and limits. Persistent application contracts remain unchanged
apart from the explicit optional Ozon pacing parameter. Keep task findings here.

User extended the experiment to compare C (1, None) with D (5, None),
then explicitly requested continuing. B is excluded from this next comparison.
Use C/D/D/C, 30-second pauses, the same frozen 40 SKUs and visible existing
Chrome profile; retain all stop conditions and recovery. No production policy change.

## Implementation and verification plan

- [x] Implement optional pacing and verify real transport invariants synthetically.
- [x] Implement three-mode runner, fixed dataset, metrics and bounded stop behavior; verify synthetic orchestration.
- [x] Run live discovery and A/B/C/C/B/A comparison, or document a reproducible blocker and ask for a decision.
- [x] Add selectable C/D/D/C order and verify D (5, no pacing); run on the same fixed 40 SKUs.
- [x] Update guide and assess results; run relevant Ozon and application regression checks.
- [ ] Inspect/stage/commit task files, refresh existing indexes/pages and present for acceptance.

## Execution state

Design approved in chat. Optional Ozon pacing and experiment runner implemented;
guide updated. Seven new synthetic experiment tests pass, including real dispatch
timings for A/B/C, unpaced cooldown/recovery/cancellation, challenge and second
refusal stopping, fixed six-batch order, and insufficient-dataset rejection.
Initial focused Ozon/application suite: 72 tests, 6 DB tests skipped, no failures.
Focused transport/CLI suite outside sandbox: 41 tests, 1 DB test skipped, no
failures (sandbox invocation hung). Compileall, CLI --help, diff --check and strict OpenSpec validation
passed. First live headless attempt stopped during dataset discovery: first
composer request for 1604900984 returned HTTP 403, then storefront preparation
reported challenge. No fixed dataset and no comparison batches were produced;
/tmp/ozon-dispatch-live-20261108.json preserves sanitized partial metrics.
Visible A/B/C/C/B/A completed: 240/240 successful cards, all composer HTTP 200,
no retries, 429 or recovery. Mean batch time A 7.577s, B 8.438s, C 7.107s.
C averaged 6.2% faster than A; two runs per mode are inconclusive. All per-SKU
field presence/count summaries matched; SKU 2056350478 was out of stock without
a price in every run. Raw evidence: measurements.json beside this spec.
C/D/D/C completed on the identical frozen dataset, without rediscovery, visible
Chrome, 30s pauses. Raw sanitized report: measurements-cd.json. Times: C 6.367919s,
D 1.347759s, D 1.500578s, C 5.471204s. Means C 5.919561s, D 1.424168s:
D is 4.1565x faster (75.94% less batch time). All 160 cards successful; all 160
composer calls HTTP 200, no 429/retries/recovery/cancellation. Actual peaks C=1,
D=5. Per-SKU field presence/count summaries match across all ten batches; actual
price values/content equality is not measured. Two runs per mode, warmed related
SKUs, cache/network/session variation and batch bootstrap limit generalization;
this establishes short-batch benefit, not sustained throughput or access reliability.
No live user DB access or production default changes. Guide documents --order C D D C,
visible mode, existing profile and retained cooldown/stop policy.
Final focused regression suite: 85 tests, 7 DB-dependent skips, no failures.
Strengthened mode test additionally passed (7 experiment tests): seven requests
exceed the five-token burst and distinguish unpaced D from paced A, measuring
actual peak five vs one. Compileall, CLI help, diff --check and strict OpenSpec
validation passed. Acceptance remains pending; next is commit and knowledge refresh.
Harness implementation committed as bf80cc9 before the user's profile correction;
Profile correction committed as 3eb289a. Both commits received CodeGraph sync
and Repowise index refresh; local checkpoints matched HEAD. Model generation is
disabled; deterministic structural pages refreshed. MCP stale target remains a
separate limitation. Documentation and experiment defaults follow the user's
explicit existing-profile instruction. No owner process was found for
~/.local/share/price-watch/chrome-profile during the preflight check.
