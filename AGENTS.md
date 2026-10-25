# price-watch — Agent Instructions

Desktop price tracker: React/Tauri, FastAPI, Python worker, PostgreSQL/Alembic,
Chrome collection, CLI, and database-free single-product JSON mode.

## Working scope

- Inspect only the code, tests, OpenSpec artifacts, ADRs, and guides relevant to
  the task. Check source before relying on documentation; reuse findings already
  established unless the code or question changed.
- Use `codegraph_explore` first for code navigation and impact. Use Repowise for
  architecture, history, risks, and affected tests. Avoid duplicate queries;
  verify critical findings in current source, especially Tauri `invoke` paths.
- Keep changes focused and preserve required product behavior unless the approved
  plan changes it. Do not invent contracts or add needless dependencies.
- Use `$vibe-flow` for substantial features, cross-component work, and architecture
  changes. Small isolated fixes can use a direct workflow without OpenSpec. Keep
  human review before implementation and before completion.

## Architecture and compatibility

- Backward compatibility is not a project goal. When replacing a solution,
  migrate all affected consumers to the new design and remove the superseded
  code, interfaces, configuration, tests and documentation. Do not keep legacy
  branches, compatibility adapters, deprecated endpoints or fallback paths for
  the old solution. Make the transition complete and permanent; do not retain
  the old implementation as a rollback option. This does not authorize deleting
  user data: migrate required persisted data safely under the rules below.
- Architecture can change. For a significant change, inspect the current design,
  compare options, propose an ADR, obtain approval, then implement through OpenSpec.
  Update relevant architecture documentation afterward; do not rewrite old ADRs.
- Check affected consumers and execution paths: desktop UI, API, worker, collection,
  persistence/migrations, CLI, and database-free JSON mode. For collection changes,
  check queued desktop/API/worker collection, `main.py collect`, and numeric Ozon ID
  mode separately. The numeric mode needs no `DATABASE_URL`, but both CLI imports
  must remain available. Demo UI uses a mock API and does not verify live services.

## Data and verification

- Preserve price history and avoid duplicate records. Deleting a card cascades to
  history; import may compact it. Review data effects and migrations before use.
  Require explicit approval for destructive operations. Never test on user data;
  PostgreSQL integration tests need a separate disposable `TEST_DATABASE_URL`.
- Run relevant existing tests and applicable lint/type checks. Verify affected
  contracts and modes; report checks that could not run. Frontend E2E covers the
  demo UI only. Commands: `docs/guide/TESTING_AND_TROUBLESHOOTING.md`.
- Update only documentation whose subject changed. Report changes, verification,
  compatibility or migration concerns, and remaining risks. Never claim a check
  passed without running it.

@RTK.md
