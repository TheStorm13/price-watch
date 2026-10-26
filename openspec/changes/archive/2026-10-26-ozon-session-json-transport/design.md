# Design

## Context

See proposal.md and research.md. The current client already fetches composer JSON through JavaScript; the avoidable cost is navigating to every product first. The live price-watch profile successfully returned the existing normalized contract from a home-page fetch on 2026-10-26. An isolated fresh system-Chrome session returned 403 JSON, demonstrating why successful JSON decoding alone is insufficient.

## Goals / Non-Goals

**Goals:** Reuse one storefront page, remove product navigation, keep the full existing model and preserve profile state. Make request failures bounded and observable. Keep numeric/raw CLI and queued/direct collection on the same transport.

**Non-Goals:** Search, review bodies, new price meanings, SKU-specific rating substitution, full characteristics enrichment, delivery setters, user-data migration, frontend redesign, independent HTTP transport.

## Decisions

1. Proposed ADR: `docs/adr/0006-ozon-session-json-transport.md`. Keep external system Chrome, CDP connection and the existing profile shutdown protocol. Create a single owned page, navigate to `https://www.ozon.ru/` at session bootstrap, and reuse it. Request `GET /api/composer-api.bx/page/json/v2?url=<percent-encoded /product/{sku}/>` with no body. Do not navigate product pages, use APIRequestContext, transfer cookies, delete storage or clone the profile.

2. Preserve asynchronous parallel collection with default concurrency **5**, explicitly requested by the user. Outer collection keeps its five-target bound; the Ozon transport also bounds actual in-flight fetch calls at five, including direct client callers and retries. Run independent async page.evaluate calls on the shared page; no lock may cover the full request/body read and serialize them. Coordinate bootstrap once, then let five requests overlap. Use an independent dispatch limiter initially allowing 5 starts per second with burst capacity 5 (including retries); there is no mandatory 1-second gap between individual requests. This is a tunable local policy, not an Ozon limit. Expose validated keyword-only transport settings if needed without changing existing call sites. Verify that five requests can all start before any completes and a sixth waits. Benchmark against the old path at the same concurrency.

3. Use a separate AbortController and request ID for every fetch/body read with a 30-second request timeout, clear its timer/registry entry in finally, and retain a slightly longer Python timeout for a nonresponsive evaluation. Return HTTP status, content type, final URL/redirect state and Retry-After with the raw text to Python. Never log the body, tokens, cookies, arbitrary headers or private URLs. Individual cancellation aborts only that request before releasing its slot; it must not close the shared page or cancel neighbors. Whole-session cancellation drains/cancels all owned requests before page/browser shutdown.

4. Permit at most three HTTP attempts per product. Retry transient network/timeout and 5xx with bounded backoff; retries use the same concurrency and dispatch limits, releasing in-flight slots during backoff. A 429 sets a shared monotonic cooldown using Retry-After in delta-seconds or HTTP-date form; concurrent 429 responses can extend but never shorten it. Already-sent requests may finish; every new dispatch/retry must recheck the shared deadline. A valid wait beyond the automatic wait budget yields RateLimited with retry_after, without retrying early. Invalid Retry-After uses the configured fallback.

   Session recovery is single-flight, with at most one automatic refresh per collection session: atomically pause new dispatches, let existing requests finish within their own bounded timeouts, then refresh the home page once in the same context/profile. Concurrent access failures join the same recovery operation/generation instead of each reloading. Resume waiting requests after success, preserving each request's attempt budget and successful neighbor results; propagate a shared recovery failure without a reload storm. Never navigate the shared page while another fetch is still active. Do not clear profile storage or repeatedly relaunch after persistent rejection.

5. HTTP status is checked before document parsing. Recognize access failures even when their body is JSON. HTML/access redirects permit one storefront session refresh; persistent rejection raises MarketplaceUnavailable with actionable text. Malformed JSON and unexpected composer structure raise MarketplaceSchemaChanged. A bare 404 is not ProductNotFound. Preserve the parser's existing narrow evidence for a removed product (search page with the matching product_id), rather than treating arbitrary search or empty widgets as absence. A typed widgetStates object alone is insufficient for normalized success; existing identity/title checks remain in force. Raw preserves original text of valid composer responses, with transport validation applied even when fetch_product_async passes validate=False.

6. Preserve parser/mapper field priorities exactly (research.md). No widget enrichment requests are needed by the observed current contract. Session bootstrap/recovery can inspect the home page to recognize challenges; product data never comes from DOM. Keep terminal/database challenge handlers and bounded headless/virtual-display failure. Update messages to point to the shared storefront tab. Lazy standalone calls use the same session lifecycle; explicit collection sessions remain shared. Always finish through existing CDP Browser.close and process wait handling.

## Risks / Trade-offs

- [Undocumented Ozon schema or regional variation] → explicit shape/identity validation, deterministic fixtures and opt-in live profile verification; preserve original field priorities.
- [Five requests share one page and session] → independent request cancellation, a shared cooldown and coordinated recovery after in-flight requests drain; deterministic overlap/race tests plus live verification. Preserve concurrency 5 rather than silently serializing to avoid races.
- [A failed request might overwrite history] → transport failures never become ProductNotFound; test collection persistence error behavior.
- [Session recovery could lose address/login] → reuse the same context/profile; do not clear cookies or storage. Verify normal shutdown and subsequent request.
- [Raw mode has historically weaker validation] → keep original successful response bytes/text; reject access and malformed data consistently rather than printing them as success.
- [Live evidence covers two individually requested in-stock SKUs, not a concurrent batch] → verify actual five-request overlap and repeated requests during implementation; other error statuses remain synthetic unless observed, clearly labeled.

## Migration Plan

After explicit plan approval, replace per-product tab transport and its tests, run focused then full Python checks, and repeat live browser verification. No database migration or persisted snapshot rewrite. Do not retain the old product-navigation path as fallback. Present the code and executed checks for acceptance; after acceptance update relevant guides/README, sync and archive specs, inspect the staged diff, and commit only task changes. Do not push or merge.
