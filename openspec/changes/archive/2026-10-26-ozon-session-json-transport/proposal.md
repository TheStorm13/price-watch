# Proposal

## Why

Ozon collection already reads composer JSON, but opens and closes a product tab before every request. Reuse a storefront session page and call the JSON endpoint directly to remove product navigation and its asset/hydration cost.

## What Changes

- Bootstrap one Ozon page per collection session in the existing managed Chrome profile; request products asynchronously through concurrent browser JavaScript `fetch` calls, with `credentials: include`, without product navigation. Preserve default concurrency 5 for actual in-flight requests, not just queued tasks.
- Validate HTTP status, response type and composer schema before returning data, including raw mode. Bound request duration, request frequency, concurrent work, retries and session recovery; respect Retry-After.
- Preserve the public connector/CLI interfaces, exact raw response, Decimal price from `cardPrice`, normalized fields, profile region, user challenge flow, persistence and history rules.
- Remove the superseded per-product tab lifecycle. Do not add storefront search, review text collection, regional setters or additional product-detail operations.
- Document observed requests, field mapping and live verification separately from synthetic error tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `marketplace-product-contract`: Ozon acquisition reuses its storefront browser session, avoids product navigation and classifies request failures explicitly, without changing the product model.

## Impact

Primary implementation: `marketplace_connector/connectors/ozon/async_client.py`; transport tests in `tests/test_async_ozon.py`, contract/CLI/profile checks and focused documentation. Parser changes only if response validation requires them, with existing mapping semantics preserved. Desktop/API/worker, direct collect and database-free numeric mode all use this client. No frontend/Rust API, dependency or database migration is expected.

Acceptance: one shared session page, zero per-product navigations, default concurrency 5 with demonstrated overlapping requests and no hidden serialization, validated JSON for valid products, typed failures for access/timeout/throttling/schema problems, bounded cancellation-safe lifecycle, preserved field/CLI/history tests, and real browser evidence in the price-watch profile. Compare request durations/navigation counts at the same concurrency without promising a speedup based on a synthetic benchmark.

Compatibility risks: stricter validation rejects malformed responses previously accepted by the transport; raw remains the original successful response text. Bare HTTP 404 must not become out_of_stock without product-specific evidence. Profile authorization and delivery region must survive recovery and shutdown.
