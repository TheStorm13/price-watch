# Cleanup notifications and tests

## Request and review gate

2026-11-02: audit old migrations, questionable functionality and redundant tests; remove manual screenshot review, deal-count notification and the strip between collection text and progress. Vibe-flow selected. Plan prepared; implementation approval and final acceptance are pending. Application code unchanged.

## Plan

See openspec/changes/cleanup-notifications-and-tests/{proposal,design,tasks}.md and its delta specs. Remove the complete notification subsystem while preserving terminal collection catalog refresh; correct footer styles locally; replace screenshot acceptance with automatic assertions and remove proven duplicate tests only.

## Evidence and retained items

- CollectionProvider.tsx:97–114 delegates successful terminal catalog fetches to DealNotifications; replacement must explicitly invalidate catalog for every terminal status.
- dealNotifications.ts:4–35,72–92 owns current/old storage readers, retry queue and extra requests, all unnecessary after notification removal.
- ActiveCollectionPanel.tsx:71 uses shared CardFooter, whose card.tsx definition supplies border-t/bg-muted/50. Verify this suspected strip with computed-style checks during implementation.
- frontend/e2e/*.spec.ts writes many PNGs to /tmp; catalog.visual.spec.ts duplicates catalog/forms/groups/details/panel journeys and depends on manual baseline acceptance documented in TESTING_AND_TROUBLESHOOTING.md:47–79. Retain unique behavioral/layout coverage before deletion. Failure screenshots can remain diagnostic.
- Revisions 0001–0018 form a continuous down_revision chain; startup MigrationRunner.apply upgrades head. Removing intermediate files would break upgrades. 0008 archive state is consumed and removed by 0010; historical code is required to transform old data.
- test_reliability_migration protects target/history/error preservation; Ali/WB migration tests protect different marketplace identities; diagnostics migration tests protect retention and atomic rejection. Repeated private-schema setup is a consolidation candidate, not evidence that assertions are redundant.
- MigrationRunner.apply:31–43 stamps an unversioned existing marketplace_cards schema as 0001. This is a compatibility adoption path and risk to record; do not silently remove it or operate on user data under this plan.

## Checks and next action

Planning validation pending. No application tests run during this read-only audit/planning phase. Repowise was stale; an index-only working-tree refresh was started, and critical claims were checked in current source. Next: obtain explicit approval of the concrete plan, then implement using the apply workflow and commit before evaluation.
