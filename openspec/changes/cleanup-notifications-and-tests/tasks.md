# Tasks

## 1. Remove deal notification subsystem

- [ ] 1.1 Remove DealNotifications, provider/shell notification state, storage migration readers and notification-only tests; verify no production references remain and provider tests cover catalog invalidation for all terminal statuses and no banner with old saved queue state.
- [ ] 1.2 Replace the notification layout E2E with relevant catalog-refresh/absence assertions, retaining deal filter behavior; verify focused unit and mock E2E tests pass and update affected notification guide text.

## 2. Correct collection footer

- [ ] 2.1 Remove inherited footer tint and divider locally; verify computed style assertions and existing layout tests for running, waiting, long challenge and expanded errors on 1024/1440 windows, without overlap or inaccessible actions.

## 3. Simplify verification and document audit

- [ ] 3.1 Map visual scenarios to behavior/layout assertions, add only missing useful assertions, remove snapshot suite/config/baselines/script and unconditional PNG writes; verify no manual screenshot acceptance is needed and mock E2E still covers forms, groups, details and collection states.
- [ ] 3.2 Review related tests for duplicated assertions/setup, consolidate only proven redundancies and retain distinct marketplace/migration contracts; verify affected Python/frontend tests and record retained/deleted scenarios with reasons in the workflow audit.
- [ ] 3.3 Record migration-chain findings, historical archive transition and unversioned-schema adoption risk; verify current source references and revision continuity, retain migrations and user data, and report any further behavior change as a separate approval decision.
- [ ] 3.4 Update the testing guide to automatic behavior/layout verification and diagnostic failure artifacts; verify documented scripts match package configuration.

## 4. Integration and evaluation

- [ ] 4.1 Run frontend unit/type/mock E2E, relevant Python tests and desktop build; run affected PostgreSQL tests only with disposable TEST_DATABASE_URL, reporting omissions and failures accurately.
- [ ] 4.2 Review diff and Repowise change risk, commit all task changes, verify commit hashes and present changed files/checks/risks for explicit user acceptance.

## Workflow follow-up

- After acceptance, sync specs, update only affected documentation, archive the change and commit the follow-up. Do not push or merge.
