# Remove seven-day deal wait

- Plan: Remove the card creation-age check from PostgreSQL and demo deal selection; keep all price-history and availability conditions. Add a recent-card integration case and update the deal guide. See `openspec/changes/archive/2026-10-21-remove-seven-day-deal-wait/`.
- Planning review: User approved the plan on 2026-10-21.
- Completion review: User accepted the implementation on 2026-10-21.
- Current state: Completed. Age condition removed from PostgreSQL and demo providers; regression tests added; deal guide updated; all four implementation tasks completed; main `deal-selection` spec synced; change archived.
- Checks: `openspec validate remove-seven-day-deal-wait --strict`, frontend lint, 84 Python tests including PostgreSQL integration on a disposable container, 20 frontend unit tests, 23 demo E2E tests, and `git diff --check` passed.
- Final checks: `openspec validate --specs` passed (5 specs); the change's strict validation passed before archive. No migration was needed.
