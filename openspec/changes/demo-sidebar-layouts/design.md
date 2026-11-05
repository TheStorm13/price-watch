# Design

## Context

The shell owns desktop chrome and the collection panel; CardsPage owns catalog state and controls. The existing E2E mode provides an in-memory mock API and a queued/running/verification/completed collection flow.

## Goals / Non-Goals

Refine the user-selected second layout with real catalog interactions and the existing design system. Do not deploy a final layout, add navigation sections, change scheduling or connect the preview to user services.

## Decisions

- Enable a lazy-loaded preview only in development with mock API mode. Provide `dev:demo` and `sidebar=2` for reproducible entry. Remove layout 1 and the comparison bar after the user's selection.
- Use contextual portal targets for existing filters and group creation. This retains URL filters, handlers, selection and group dialogs in their existing owner. The preview shell owns global add/collection/import actions so they remain available in product details too, reusing existing dialogs and collection commands. Duplicating CardsPage would drift; lifting all catalog state into the shell would unnecessarily refactor production behavior.
- Keep a 260 px sidebar. Its middle scrolls independently; tools and collection status remain below it. Reuse collection UI rather than inventing parallel run state.
- Keep name/article search above results with no catalog title/subtitle. Put sorting first among sidebar filters. Use compact popovers with grouped checkboxes for marketplace/tag multi-selection and one inline availability checkbox. Missing selection parameters mean all, explicit empty selection means no matches. Tags match OR; all includes untagged products.
- Keep demo filtering/sorting in a dedicated pure module, leaving production filter contracts intact. Preserve the current default deal logic, but bypass its priority partition for explicit price ordering. Null prices stay last in either direction. Disable additional header sorts in the demo. Filter groups using their representative as the current catalog does; sort group members by the same selected order.
- Seed only the opt-in mock preview using existing mock update/import contracts, with tags and two additional marketplace samples. Normal E2E, performance fixtures and desktop data are unaffected.
- Label desktop-only actions as simulated in dialogs. Import/export continues to operate on mock data.
- Use installed primitives, system fonts and semantic tokens. No new visual assets or application architecture ADR is needed for this bounded preview.

## Risks / Trade-offs

- Narrower results → inspect table scrolling and sticky action columns at 1024×768 and 1440×900.
- Popover controls and navigation → URL owns filters; verify combined choices, reload, detail return and keyboard focus restoration.
- Long progress/verification text → constrain panel height, retain internal scrolling, test challenge continuation.
- Shared catalog changes → run existing unit, layout and catalog E2E tests plus the production frontend build.

## Migration Plan

No data migration. This is an explicitly requested demo mode, not a legacy production fallback. The final production layout is a separate decision after review.
