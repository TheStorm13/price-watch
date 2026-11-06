# Cleanup notifications and tests

## Request and review gate

2026-11-02: audit old migrations, questionable functionality and redundant tests; remove manual screenshot review, deal-count notification and the strip between collection text and progress. Vibe-flow selected. User explicitly approved the plan with «Да» after planning commit 55f5aa5. Implementation is in progress; final acceptance is pending.

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

## Implementation and audit decisions

- Removed DealNotifications, its entire test file, notification context fields/banner and obsolete localStorage adapters. CollectionProvider invalidates catalog for completed/completed_with_errors/failed using the existing query lifecycle. No new compatibility path or replacement subsystem.
- Collection footer alone overrides its inherited background/top border. Automated CSS checks verify transparency, zero border width and no shadow, alongside existing scrolling/bounds checks.
- Removed 31 unconditional screenshot statements, five visual tests, 14 PNG baselines, visual configuration and test:visual script. Failure screenshots/traces remain diagnostics. Removed unused group/run fixture branches formerly needed only by the visual suite.
- Consolidated duplicated private-schema setup from AliExpress and Wildberries migration tests into tests/migration_support.py. Kept both marketplaces' different seed data and all preservation/conflict/active-run assertions. Other migration tests check different contracts and remain intact.
- Reviewed the full 18-revision chain: one head 0018_product_variants, one base 0001_initial, no missing parents, branches or cycles. Startup still upgrades head. Historical migrations are retained, including 0004 price-plateau compaction, 0008→0010 archive-state conversion, 0013 tracking-to-deal participation rename and 0014–0018 identity/targets/diagnostics/variant transitions. Age and temporary historical columns are not evidence of removable migrations. No application database code or migration was changed.
- Suspicious unversioned-schema adoption in MigrationRunner remains a separately documented risk: table presence alone is used to infer revision 0001. Removing or tightening it changes upgrade behavior and needs a separate reviewed decision. No user data was inspected or migrated.

### Coverage retained after removing visual journeys

| Removed screenshot journey | Automatic coverage retained |
| --- | --- |
| Catalog list/grid, single filtered result | app.spec.ts view switching, filtering, sizing and overflow checks; usability.spec.ts alignment and tags |
| Add drawer/group dialog | app.spec.ts core flow and group management; usability.spec.ts form error/action/focus checks |
| Long product details at 1024/1440/1920, edit drawer | usability.spec.ts long-name/large-price layout; variants.spec.ts variant edits; layout.spec.ts tag validation and focus |
| Group list/grid | app.spec.ts group transitions; group-metrics.spec.ts representative filtering and tile geometry |
| Running/waiting/error panel | layout.spec.ts running/waiting/long challenge/expanded error checks at 1024/1440; ActiveCollectionPanel.test.tsx progress/diagnostic/action contracts |
| Notification banner | Replaced by no-banner E2E with old saved state; provider tests check terminal refresh, dismissal and ignored saved queue |

## Checks and next action

Passed: strict OpenSpec validation, frontend typecheck, all 78 frontend unit tests, all 59 mock E2E (3.6 minutes), three focused collection/layout E2E and all 229 Python tests with TEST_DATABASE_URL pointing to a newly initialized temporary PostgreSQL cluster (56 seconds). Desktop release build passed. The temporary database server was stopped afterward; no user data was used. Preserved the visual suite's explicit Vite-overlay assertion in the existing core E2E and reran that scenario after the final edit.

Browser plugin not available; existing Playwright is the selected validation path. Tested UI runs at http://127.0.0.1:5175 using mock API; footer checks cover 1024×700 and 1440×900, detail layout also covers 1920 width. Per user request no manual PNG acceptance is used. E2E logged a non-fatal React Router HydrateFallback warning; it reported no test failures. Native Tauri interaction and live marketplace collection were not rerun; the desktop binary was built and Python browser/transport tests ran against isolated fixtures.

Repowise change review found no introduced/worsened findings in compared code. Its verdict was partial/unknown because 14 deleted PNGs cannot be analysed as code. Reviewed all deleted baseline names against the coverage mapping above; no screenshot consumers or visual-script references remain in active code/guides. Local index refreshed without model generation; MCP historical metadata still advertises an older index, so current source and executed tests provide the primary evidence. Reviewed the full textual diff and whitespace checks.

Implementation and checks are complete; all task changes are included in the implementation commit created in this run. Awaiting explicit user acceptance. Sync/archive remains deferred until acceptance.
