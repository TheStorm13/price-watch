# Tasks

## 1. Initial interactive comparison (completed historical stage)

- [x] 1.1 Add opt-in mock-only sidebar shell, portal slots and demo launch command; document entry links and scope in the workflow record.
- [x] 1.2 Relocate existing actions and filters per variant; cover filter preservation and working group creation in E2E.
- [x] 1.3 Anchor existing collection UI at the sidebar bottom; verify challenge, completion and independent scrolling at supported desktop sizes.

## 2. Integration verification

- [x] 2.1 Run frontend type check, unit tests, affected E2E and production frontend build; inspect rendered layouts and console output.
- [x] 2.2 Review diff and risk, prepare the verified implementation commit for user evaluation.

## 3. Selected layout refinement (approved by user)

- [x] 3.1 Remove the old «Карточки» heading/subtitle and comparison bar (the final «Карточки товаров» heading is added in 4.1), move article search above results and replace sidebar filters with the approved controls.
- [x] 3.2 Implement demo-only multi-selection/OR matching and three sorting choices; add representative mock samples and verify semantic edge cases.
- [x] 3.3 Verify combined filters, reload/detail return, group creation, keyboard interaction and bottom progress in E2E at supported desktop sizes.
- [x] 3.4 Run relevant unit/type/build/regression checks, review rendered UI and diff, update workflow evidence and prepare the checked revision commit for evaluation.

## 4. Selection controls and catalog heading (approved by user)

- [x] 4.1 Add «Карточки товаров», replace common checkboxes/headings with bulk actions and enforce a nonempty marketplace selection.
- [x] 4.2 Make empty tags display «Без тегов» and match untagged products; include a sample and update unit/E2E coverage for bulk, last-choice and reload behavior.
- [x] 4.3 Run relevant checks, inspect popup/layout states at supported sizes, update workflow evidence and prepare the verified revision commit for user evaluation.

## 5. Approved group/count/navigation follow-up

- [x] 5.1 Filter individual cards, including all group members, against the complete combined predicate; build tag choices from all cards. Keep groups with matches and show only matching members when expanded.
- [x] 5.2 Derive the group summary from its first matching member in current sort order; show matching/total member counts, e.g. «2 из 5 товаров».
- [x] 5.3 Count individual cards in «Выбрано n из m товаров», including grouped cards once; keep checkbox-selection and collapse state independent of this count.
- [x] 5.4 Render Price watch as plain text; preserve the explicit details-to-catalog return link and its search/filter/view context.
- [x] 5.5 Verify member-only matches, predicates split across different members (must not match), zero matches, representative changes by sort, totals under grouping/collapse/checkbox selection, tag discovery and navigation context. Review and commit the implemented delta before user evaluation.

## Workflow follow-up

- The approved follow-up is implemented in the isolated demo; production adoption remains separate.
- Wait for explicit user acceptance before syncing specs and archiving this change.
