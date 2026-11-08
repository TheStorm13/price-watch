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
explicit repo path; its risk output is not used as current evidence. Local state
has HEAD f1d4c01 for both index and docs checkpoints, docs_enabled=false.

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

## Implementation and verification plan

- [x] Implement optional pacing and verify real transport invariants synthetically.
- [x] Implement three-mode runner, fixed dataset, metrics and bounded stop behavior; verify synthetic orchestration.
- [ ] Run live discovery and A/B/C/C/B/A comparison, or document a reproducible blocker and ask for a decision.
- [ ] Update guide and assess results; run relevant Ozon and application regression checks.
- [ ] Inspect/stage/commit task files, refresh existing indexes/pages and present for acceptance.

## Execution state

Design approved in chat. Optional Ozon pacing and experiment runner implemented;
guide updated. Seven new synthetic experiment tests pass, including real dispatch
timings for A/B/C, unpaced cooldown/recovery/cancellation, challenge and second
refusal stopping, fixed six-batch order, and insufficient-dataset rejection.
Initial focused Ozon/application suite: 72 tests, 6 DB tests skipped, no failures.
Focused transport/CLI suite outside sandbox: 41 tests, 1 DB test skipped, no
failures (sandbox invocation hung). Compileall, CLI --help, diff --check and strict OpenSpec validation
passed. No live traffic yet. Production defaults and other marketplaces unchanged;
queued/direct/numeric behavior checked by existing relevant tests, not live demo UI.
Working tree initially clean. User acceptance not requested or received. Next:
commit the verified harness and refresh knowledge, then
run live discovery/comparison with the existing Price Watch profile and preserve results.
Harness implementation committed as bf80cc9 before the user's profile correction;
post-commit knowledge refresh is pending. Documentation and experiment defaults now
follow the user's explicit existing-profile instruction. No owner process was found
for ~/.local/share/price-watch/chrome-profile during the preflight check.
