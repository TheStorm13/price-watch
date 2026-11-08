# Task: Ozon unpaced async collection at fixed N=8

## Goal and acceptance criteria

Current scope, selected by the user after the experiments: implement ordinary
Ozon collection with async I/O, no planned start-rate limit and fixed N=8.
Other connectors are the next task; acceptance and archival remain pending.

Original experiment scope: compare Ozon A (5 concurrent requests, 5 starts/s), B (1, 5/s), C (1,
no planned start limit) on the same fixed 30–50 unique SKUs including variants.
Run A/B/C then C/B/A with pauses; retain async I/O, Retry-After, bounded retries,
timeouts and recovery. No user database access or history writes. AliExpress and WB unchanged. Initial experiments did not change production policy;
the latest user instruction below explicitly authorizes the N=8 rollout.

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
`price_watch/application/collection_service.py`: originally five concurrent card attempts;
now eight for Ozon and a shared pool of five for other platforms.
`marketplace_connector/application/retry.py`: one additional application retry.
`experiments/parallel_ozon.py`: instrumented DB-free A/B/C/D and numeric
5/8/12 comparison, actual request concurrency and resource sampling. `docs/tasks/ozon-session-json-transport.md`
records five historical live SKU seeds; availability today is unverified.
Backlog retains pre-acceptance rollout context; do not update its completion status before acceptance.
CodeGraph returned current source. Repowise MCP targets obsolete 9f3876d despite
explicit repo path; its risk output is not used as current evidence. Local CLI index refresh is used instead; docs_enabled=false (deterministic pages only).

## Agreed solution

User approved the three-mode experiment on 2026-11-08 ("Да"), after selecting
Ozon only. Retain all failure handling; remove only planned pacing in C.
Support starts_per_second=None in Ozon client/transport, preserving positive finite
validation for numeric limits. None bypasses token accounting, not cooldown or
concurrency. At that experiment stage production callers kept default 5/s; the latest rollout changes it to None. This parameter is local policy,
not a claim about Ozon's published limits. No architectural boundary changes; the selected direction is recorded in ADR 0014.

Replace existing experiment with instrumented real transport/client use. Instrument
only the experiment via a transport subclass/factory; do not store response bodies,
cookies, tokens, addresses or exception strings that could contain them. Capture
per-target logical attempts and per-dispatch queue/network timings separately;
composer counts exclude navigation/background browser traffic and are labelled.
Use the shared application retry policy; original A/B/C/D use five logical card
workers, numeric fixed-N modes use N workers to avoid a hidden ceiling.
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
metric definitions and limits. At the experiment stage persistent application contracts remained unchanged
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
- [x] Commit the measured A/B/C and C/D experiment results (a0c5fd5).
- [x] Agree fixed N=5/8/12 comparison without planned pacing (user requested proceeding).
- [x] Implement and verify fixed-N dispatch and resource measurements.
- [x] Run repeated 5/8/12 forward/reverse comparison on the frozen 40 SKUs (completed with two failed batches).
- [x] Assess results and identify remaining sustained-behavior validation.
- [x] Apply the user-selected production policy: Ozon defaults N=8, no planned pacing, including queued/direct collection.
- [x] Verify default dispatch overlap, mixed-marketplace isolation, retry/cancellation and CLI/worker paths.
- [x] Update durable policy/architecture documentation and preserve fixed-N evidence.
- [ ] Explicit user acceptance of the committed rollout (commit/index checkpoints reported in delivery).

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
validation passed. Results committed as a0c5fd5. The task remains open; final acceptance has not been given.
Harness implementation committed as bf80cc9 before the user's profile correction;
Profile correction committed as 3eb289a. Both commits received CodeGraph sync
and Repowise index refresh; local checkpoints matched HEAD. Model generation is
disabled; deterministic structural pages refreshed. MCP stale target remains a
separate limitation. Documentation and experiment defaults follow the user's
explicit existing-profile instruction. No owner process was found for
~/.local/share/price-watch/chrome-profile during the preflight check.

## Fixed-N experiment and subsequent user choice

User explicitly requested keeping this task open. The previous archive was an
agent interpretation, not user acceptance. Restored active context and raw
measurements. The selected direction (async, no planned rate limit, finite N)
remains recorded in ADR 0014; N=5 is a tested point, not the selected optimum.
Production defaults were unchanged during those measurements; the subsequent user choice authorizes N=8 rollout.

User approved proceeding with fixed-N comparison on 2026-11-08. Run N=5/8/12
without planned pacing on the same frozen 40 SKUs, existing visible Chrome profile,
30s pauses. Two forward/reverse cycles (5,8,12,12,8,5 repeated twice) give four
batches per N. No automatic escalation to 16 in this stage. Preserve all original
stop/recovery rules and no-DB behavior. Match logical worker count to N above five;
keep original A/B/C/D behavior for reproducing earlier results. Record actual peak
requests, field completeness, latency/queue times and sampled Chrome process-group
CPU/RSS on Linux, with sampling/shared-page accounting limitations explicit.
Compare only within this series. The smallest N reaching 95% of best healthy
throughput is an analysis candidate, not an automatically selected production
setting. The user subsequently chose N=8 explicitly. Sustained-load validation
remains a limitation; no adaptive controller is introduced. Task acceptance and archival remain pending.

Fixed-N implementation verified before live launch: 31 transport/experiment tests
passed, including barrier-based proof that 5/8/12 requests actually overlap,
resource group isolation/accounting and fixed dataset/order orchestration.
Focused Ozon/application/CLI regression: 87 tests passed, 7 DB-dependent tests
skipped. Compileall, CLI help and strict OpenSpec validation passed.
Fixed-N series finished: first ten batches 400/400 successful with HTTP 200 and no retries/recovery; last two (N8, N5) failed all 80 targets during session preparation, with zero composer dispatches. Log reports closed browser/context; who or what closed it is unverified. Full sanitized evidence is measurements-fixed-n.json. Do not average the failed batches as throughput. The first N5 batch overlapped the local regression suite; timing comparison is confounded. This is not sustained-reliability proof.


## Agreed production rollout: fixed N=8

After reviewing the fixed-N findings, the user explicitly instructed: “Я получил достаточно информации. Давай перепишем текущую реализацию ozon на асинхроннсоть без лимитом и парарллельность 8.” This authorizes implementation of the selected async/unpaced design at N=8; it is not final acceptance or permission to archive. Other connectors are a subsequent task. Supersedes earlier experiment-only scope and the statement that production rollout is unauthorized.

The transport is already asynchronous; change its production defaults to 8 concurrent composer requests and starts_per_second=None. Keep one session-scoped budget shared by product, aspect-modal and retry requests. Retain explicit numeric pacing solely to reproduce the existing experiment controls; ordinary builder/numeric CLI callers use the unpaced default, with no automatic fallback to 5/s. Retain cooldown/Retry-After, bounded retries, preparation/recovery, cancellation and existing response validation.

Remove the application's hidden five-card ceiling for Ozon by giving its card attempts a dedicated eight-slot semaphore. Other marketplaces continue sharing their existing five-slot pool. Retry sleep releases its card slot. Mixed runs may have eight Ozon attempts plus five other-marketplace attempts; existing transports still enforce each platform's request limits. Share the Ozon concurrency constant between client, transport and collection policy to prevent drift. One registry/builder client per marketplace preserves the single transport budget; do not add clients per card.

Acceptance criteria: default transport reaches eight simultaneous requests and never nine; subsequent sends wait only for capacity or recovery/cooldown, with no token pacing; default client/builder/numeric CLI inherit the same policy; queued desktop/API/worker and main.py collect reach eight Ozon attempts, while mixed runs preserve the other-marketplace pool of five. Existing cancellation, lease ownership, retries, data mapping, raw JSON and database-free imports remain valid. No data migrations, user DB access, Chrome-profile reset, adaptive N or other connector changes.

Verification: barrier-based real-transport fake-page test for default N8 and ninth-request exclusion; mixed-run barrier test for eight Ozon plus shared five WB/Ali slots; focused existing Ozon/CLI/collection/retry/connector suites, import/CLI help with DATABASE_URL absent, compileall, diff/OpenSpec checks. Live benchmark findings remain evidence for the selected approach; no new long-running live comparison is required after the user said enough information. Update ADR0014, architecture and testing guide before acceptance. Implementation and focused verification are complete; task remains open for explicit user acceptance.


Current rollout verification: 104 focused tests, no failures, 7 DB-dependent skips
(no disposable TEST_DATABASE_URL supplied). Default transport and builder client
prove eight overlapping fetches and ninth-request exclusion with fake browser pages.
Mixed-run barrier proves eight Ozon attempts plus at most five combined WB/Ali
attempts. Retry-wait release test now spans nine Ozon targets. Existing tests cover
recovery, cooldown, cancellation, lease loss, raw/numeric mode and bounded retries.
Compileall, both main.py --help and main.py <numeric_id> --help without DATABASE_URL,
git diff --check and strict OpenSpec validation pass. No configured Python lint/type
checker was found. Static path inspection confirms queued API → worker → RunExecutor
→ CollectionService; direct collect uses the same executor, numeric CLI constructs
AsyncOzonClient. Full PostgreSQL/desktop live execution was not rerun. No user DB
access or new live series was performed for the rollout after the user said enough
information. Tests use fakes; prior live evidence is recorded separately above.

ADR0014 and both maintained architecture guides now describe N=8/no planned pacing,
the separate Ozon card budget and unchanged other-platform pool. The testing guide
retains original experimental controls and existing-profile requirements. Numeric
pacing remains only as an explicit experimental control, not a production fallback.
Repowise risk queries still return obsolete commit 9f3876d even though local status
checkpoint is 9f427c8; these queries provide no reliable current risk evidence.
Current source and relevant tests were inspected directly following CodeGraph.
Task commit and refreshed local index/page checkpoints accompany the delivery.
No final acceptance has been given; do not archive.
