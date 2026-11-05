# Design

## Context

The shell owns desktop chrome and the collection panel; CardsPage owns catalog state and controls. The existing E2E mode provides an in-memory mock API and a queued/running/verification/completed collection flow.

## Goals / Non-Goals

Refine the user-selected second layout with real catalog interactions and the existing design system. Do not deploy a final layout, add navigation sections, change scheduling or connect the preview to user services.

## Decisions

- Enable a lazy-loaded preview only in development with mock API mode. Provide `dev:demo` and `sidebar=2` for reproducible entry. Remove layout 1 and the comparison bar after the user's selection.
- Use contextual portal targets for existing filters and group creation. This retains URL filters, handlers, selection and group dialogs in their existing owner. The preview shell owns global add/collection/import actions so they remain available in product details too, reusing existing dialogs and collection commands. Duplicating CardsPage would drift; lifting all catalog state into the shell would unnecessarily refactor production behavior.
- Keep a 260 px sidebar. Its middle scrolls independently; tools and collection status remain below it. Reuse collection UI rather than inventing parallel run state.
- Show «Карточки товаров» above name/article search without a subtitle. Put sorting first among sidebar filters. Use compact popovers with individual checkboxes and one bulk button; do not repeat visible headings or common-selection checkboxes inside them. Use an aria-label on the checkbox fieldset to preserve its accessible name.
- Missing selection parameters mean all. Require at least one marketplace: disable the last selected checkbox and use «Оставить один» when all are selected, otherwise «Выбрать все». Empty/invalid marketplace URL choices normalize to all. Tags allow zero selections: show «Без тегов» and match only untagged products; nonempty choices match OR and all includes untagged products. Tags use «Снять выбор» when all are selected and «Выбрать все» otherwise.
- Match multi-selection popup width to its trigger so it stays within the sidebar. Use compact, content-width outline bulk buttons aligned to the left. Show the matching/total catalog count only beside «Карточки товаров», as «Выбрано n из m товаров»; count individual cards, including group members, once each. The numerator is matching cards and the denominator is all catalog cards; collapsed state and bulk-selection checkboxes do not affect these values. This approved follow-up is not yet implemented.
- Open the preview's add-card sheet from the left, retaining its 420 px width, form behavior and focus restoration. Pass the existing Sheet side through the shared form wrapper; normal desktop/edit consumers keep their default right-side presentation.
- Keep demo filtering/sorting in a dedicated pure module, leaving production filter contracts intact. Preserve the current default deal logic, but bypass its priority partition for explicit price ordering. Null prices stay last in either direction. Disable additional header sorts in the demo. For the approved follow-up, filter each member against the complete predicate before composing groups. Keep a group only when it has matching members and show only those members when expanded. Sort matching members by the selected order; use the first as the summary representative, not a permanently designated best product. Show matching/total member counts. Discover tag options from all cards, including nonrepresentative members.
- Render Price watch as plain text without navigation/reset behavior. Product details retain the explicit «К карточкам» link, preserving search, filters and list/grid view. This follow-up is not yet implemented.
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

## Approved follow-up status

The user approved the group-container model, individual-product counting and noninteractive brand on 2026-11-06, and requested that these decisions be recorded. Current demo behavior has not changed in this planning revision. Implement and verify section 5 of tasks before treating the updated requirements as delivered. Production activation remains a separate change.
