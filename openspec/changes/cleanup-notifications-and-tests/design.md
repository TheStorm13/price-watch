# Design

## Context

CollectionProvider delegates catalog refresh for successful runs to DealNotifications; removing only the banner would retain unnecessary work, while removing the queue without replacement would break refresh. CardFooter supplies border-t and bg-muted/50. E2E already checks bounds, overflow and accessibility alongside unasserted screenshots; the separate visual suite requires manual baseline acceptance.

## Goals / Non-Goals

Goals: remove the notification subsystem completely and keep terminal-run refresh; make routine verification automatic. No replacement notification system, database reset, migration squashing, API redesign or unrelated feature removal.

## Decisions

- Remove DealNotifications and provider/shell notification state. Invalidate catalog for all terminal statuses using the existing query client. Remove old storage readers rather than introducing a cleanup adapter. Deal filtering remains available in the catalog.
- Override the collection footer background/border locally; do not change every shared CardFooter. The strip is a source-based diagnosis to verify with computed styles and panel geometry.
- Remove explicit screenshot writes and snapshot-acceptance workflow. Keep failure screenshots/traces as diagnostic artifacts. Remove catalog.visual.spec.ts and its config/baselines after mapping useful scenarios to existing assertions; extend layout tests only for missing coverage.
- Retain historical migration implementations: each down_revision participates in startup upgrade-to-head. 0008 adds archive state which 0010 migrates into tracking; these are historical data transitions, not current duplicate features. 0014–0018 contain preservation/abort behavior with distinct contracts. Consolidate repeated Ali/WB test schema setup or parameterize genuinely equivalent checks only if it improves clarity; retain marketplace-specific seeds and assertions.
- Record suspicious functionality as evidence-backed findings. Removing unrelated behavior requires a revised plan; static dead-code suggestions alone do not authorize deletion. No architecture change warrants an ADR here.

## Risks / Trade-offs

- Lost catalog refresh → test each terminal status and completion after dismiss.
- Loss of pixel-level regression coverage → retain deterministic layout/overflow and behavior assertions; routine checks intentionally stop judging aesthetics via PNG approval.
- Older migration tests look duplicated → compare protected data/versions before consolidation; retain distinct transition checks.
- Repository indexes may lag current variants changes → verify critical claims against disk and refresh Repowise without model generation.

## Migration Plan

No database migration or user-data operation. Apply frontend/test changes together; old notification storage is ignored. Keep historical upgrades available for existing installations. Run checks on disposable fixtures and database only. Commit task files before user evaluation; after acceptance sync/archive specs and commit relevant follow-up documentation.
