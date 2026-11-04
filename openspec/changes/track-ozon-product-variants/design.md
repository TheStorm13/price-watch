## Context

The original approved phase added Ozon family membership: separate SKU IDs share a card, linked webAspects are traversed through durable targets, and histories remain independent. The user subsequently approved selective recurring tracking and automatic initial discovery on 2026-11-04. ADR 0013 supersedes recurring-all scheduling from ADR 0012.

## Goals / Non-Goals

Obtain every reachable Ozon/WB/AliExpress variant and initial prices on creation, then collect only the primary and explicit selections. Preserve identities, metadata and history. Provide individual and bulk controls, including existing variants defaulting off. No automatic merging of independently owned cards; no hidden full traversal in numeric database-free Ozon mode.

## Decisions

1. Store `tracking_enabled=false` independently on each variant. Effective tracking is primary OR preference. The primary control is locked. Changing primary preserves preferences, so the former primary remains tracked only if explicitly enabled. WB/Ali unresolved pre-SKU records retain their history but cannot replace an available exact primary or become a recurring target.
2. Bulk actions affect known non-primary exact variants only. Newly discovered extras always default off; there is no persistent enable-future mode.
3. Persist `discover_all` on runs. Initial jobs expand reachable links and obtain exact prices for every discovered SKU; regular jobs freeze primary/enabled targets when enqueued. Discovery from regular responses retains metadata without adding disabled targets. WB/Ali unresolved bootstrap selects an exact primary and schedules it even outside an initial job. Retry preserves discovery purpose for root bootstrap; exact SKU retries remain bounded to failed targets.
4. Card creation and initial queue insertion commit atomically in the same PostgreSQL transaction. CardRepository delegates queue insertion to the injected RunRepository, sharing composition-root clock and policy. Creators acquire run-creation before membership, diagnostic and card locks. No network in the request and no frontend-only refresh. Desktop prepares the collector before creation and existing run polling observes the job. API and CLI creation enqueue without a frontend.
5. Preserve exact membership validation and Ozon global ownership checks across add/discovery/import. Merge named aspects per SKU. Never synthesize unconfirmed option combinations, overwrite exact metadata with partial neighbor data, or transfer history across variants. Ozon initial traversal is bounded to 500 SKU with explicit incomplete diagnostics; valid prices survive partial failures. Unknown continuation is reported. One browser session and existing concurrency/cooldowns are reused.
6. Transfer v3 exports explicit preferences. Newly imported variants restore them, missing values default false; merging preserves local preferences. Existing history merge rules remain unchanged. Numeric Ozon JSON/raw performs one exact request without DATABASE_URL.

## Alternatives

A card-wide boolean cannot express selected sizes/colors. Synchronous remote fetching during creation blocks requests on Chrome checks; frontend-only refresh can be lost after creation. Reuse the existing queue/executor rather than adding another queue or crawling inside every connector call.

## Migration and verification

Forward-only `0020_variant_tracking` backfills false for all existing preferences and adds default-false run purpose. It does not change IDs, primary, histories, metadata or existing queued targets. Deploy schema with new writers together; tests run only on disposable TEST_DATABASE_URL. Verify initial all-variant discovery for all three marketplaces; worker/API/CLI queueing; ordinary and scheduled target selection; primary changes, individual/bulk controls, frozen queued targets, retry, ownership and transfer. Frontend unit/lint/mock E2E and desktop build complement PostgreSQL connector integration. Mock UI is not evidence of live marketplace availability.

## Risks

Ozon storefront structure and visible assortment vary by category/profile. Discovery covers confirmed reachable links, not an unavailable storefront catalog. Unknown structure and ownership conflicts remain explicit errors. Existing run diagnostics retention applies to creation jobs as well. User history must never be deleted by tracking changes.
