# Tasks

## 1. Deal selection

- [x] 1.1 Remove the seven-day card age predicate from PostgreSQL deal selection, preserve its other conditions and public method signature, and verify a recently created card with a prior price qualifies in the disposable PostgreSQL integration test.
- [x] 1.2 Remove the age condition from the demo mock deal filter and verify frontend lint, unit tests, and affected demo behavior.
- [x] 1.3 Update `docs/guide/DATA_AND_API.md` to describe deal eligibility without a card age threshold and verify it matches the implemented conditions.

## 2. Cross-path verification

- [x] 2.1 Run the relevant Python suite and frontend checks, inspect the API response contract and diff, and report any unavailable PostgreSQL test if no disposable `TEST_DATABASE_URL` exists.

## Workflow follow-up

- After implementation review and user acceptance, sync the new deal-selection spec and archive this change.
