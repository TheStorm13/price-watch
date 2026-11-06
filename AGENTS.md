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
- Use the selected `vibe-flow` for implementation tasks. New tasks use the
  `vibe-flow` OpenSpec schema and one `spec.md`; small fixes use a short spec
  with the same two review gates. A direct path is not an exemption from the
  spec or review gates in this project. Existing changes keep their recorded schema.
- Commit verified task changes before presenting work for acceptance, including
  checked corrections requested during evaluation. The selected skill defines
  the acceptance and completion lifecycle.

## Backlog and project documentation

- `docs/BACKLOG.md` is the project's independent list of future work, outside
  the flow's spec/archive lifecycle. Read entries relevant to the current task;
  an entry is not authorization to implement it. After acceptance, update only
  the entry for the completed task. Add new ideas when the user requests it.
  Preserve unrelated user edits and keep them out of task commits.
- Existing plans, reports and their attachments live in `docs/tasks/`. Preserve
  their contents and agreed decisions; do not rewrite them into the new format
  or re-audit them as part of workflow setup. New task context and tracking live
  in `openspec/changes/<name>/spec.md`, then its accepted archive.
- Keep durable guides, architecture, ADRs and behavior specs in their existing
  locations. Update affected documents with implementation before acceptance;
  the single-file schema does not automatically sync permanent specifications.

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

<!-- agent-kit:workflow:start -->
<!-- flow: vibe-flow -->
## Workflow

Use $vibe-flow for substantial implementation tasks. Small isolated fixes may use
its direct path. An explicitly selected installed workflow governs the current
task. Do not combine lifecycle rules from different workflows.

CodeGraph, Repowise, Context7 and RTK are the baseline for this project.
Keep project-specific checks, architecture and data constraints outside this block.
<!-- agent-kit:workflow:end -->
