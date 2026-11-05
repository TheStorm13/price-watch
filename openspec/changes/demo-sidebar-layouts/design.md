# Design

## Context

The shell owns desktop chrome and the collection panel; CardsPage owns catalog state and controls. The existing E2E mode provides an in-memory mock API and a queued/running/verification/completed collection flow.

## Goals / Non-Goals

Compare placement with real catalog interactions and the existing design system. Do not deploy a final layout, add navigation sections, change scheduling or connect the preview to user services.

## Decisions

- Enable a lazy-loaded preview only in development with mock API mode. Provide `dev:demo` and query parameter `sidebar=1|2` for reproducible entry.
- Use contextual portal targets for existing filters and group creation. This retains URL filters, handlers, selection and group dialogs in their existing owner. The preview shell owns global add/collection/import actions so they remain available in product details too, reusing existing dialogs and collection commands. Duplicating CardsPage would drift; lifting all catalog state into the shell would unnecessarily refactor production behavior.
- Keep one sidebar width for both variants. The middle scrolls independently, tools and the collection panel remain below it. Reuse the collection UI rather than inventing parallel simulated run state.
- Label desktop-only actions as simulated in dialogs. Import/export continues to operate on mock data.
- Use installed primitives, system fonts and semantic tokens. No new visual assets or application architecture ADR is needed for this bounded preview.

## Risks / Trade-offs

- Narrower results → inspect table scrolling and sticky action columns at 1024×768 and 1440×900.
- Portal relocation remounts controls → URL owns filter values; compare switching with active filters and preserve dialog focus behavior.
- Long progress/verification text → constrain panel height, retain internal scrolling, test challenge continuation.
- Shared catalog changes → run existing unit, layout and catalog E2E tests plus the production frontend build.

## Migration Plan

No data migration. This is an explicitly requested demo mode, not a legacy production fallback. The final production layout is a separate decision after review.
