# Design

## Context

The demo implements the approved appearance and per-member filtering, but uses a lazy mock-only shell, portals and fake settings/Chrome. Production AppShell owns real desktop errors and invoke commands. CardsPage currently computes both old and preview models.

## Goals / Non-Goals

Make the approved UI permanent and retain real functionality. No service, data schema or scheduling redesign.

## Decisions

- Replace AppShell markup directly, keeping DesktopRuntimeContext, CollectionProvider and existing invoke commands. Move one add drawer and global group creation dialog to the shell. Keep bulk creation and group editing in CardsPage; use original full group membership when editing.
- Render catalog filter controls in the shell without portals. On details they display the saved catalog context; changing a filter opens its catalog results. Closing settings/add/group overlays leaves the detail route intact. Search remains exclusively over catalog results.
- Move preview filter/model code into cards features; use one memoized catalog model with deferred search. Keep exact-decimal comparison and null prices last. Remove obsolete single-filter and column-sort implementation/tests.
- Rename demo CSS to permanent sidebar classes and remove replaced header/filter rules. Keep compact fixed table widths, sticky trailing cells, virtualization and grid typography.
- Keep sample data in an explicit test fixture only, enabled by an E2E-only test parameter. No sidebar UI gate or fixture in desktop runtime.

Alternative: enable the demo shell in production. Rejected because it bypasses real settings, Chrome and service errors. Alternative: keep both catalog models. Rejected because filtering semantics would drift. This is a frontend ownership refactor using existing providers, not a new system architecture; no ADR is needed.

## Risks / Trade-offs

Existing mock E2E tests encode old labels, sorting, empty-group visibility and group representative behavior; migrate assertions to the agreed behavior rather than retaining compatibility branches. Real Chrome/settings commands require native runtime; test them through mocked invoke unit tests and build the desktop binary. Browser tests do not verify live services.

## Migration Plan

No persisted data or technical identifiers change. Remove demo toggle/env, portal and fake dialogs after replacing consumers. Catalog URL uses markets/tags/stock and default/price sorts only; old query keys are unsupported.

## Verification

Typecheck, unit tests, relevant mock E2E (including large catalog/navigation, collection, import/export), production Tauri build; inspect list/grid and dialogs at 1024/1440. Use disposable mock data only. Review final diff and commit before user evaluation.
