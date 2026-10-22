---
name: vibe-flow
description: Plan and implement substantial Marketplace Price Analyzer changes with OpenSpec when needed and two human review gates.
---

# Vibe Flow

One Codex handles the task. Inspect only affected code, tests, and relevant
project documents. Reuse established findings; investigate further only when
a decision or contract remains uncertain. Use OpenSpec for substantial features,
cross-component or contract changes, significant refactoring, and architecture
changes. Small isolated fixes need no OpenSpec.

## 1. Planning

Identify current behavior, affected components and consumers, risks, acceptance
criteria, and a focused test plan. Prepare or update OpenSpec artifacts when
required. For a significant architecture change, compare alternatives and
propose an ADR. Present the concrete plan and any migration or compatibility
effects. **Wait for explicit user approval before changing application code.**
If the plan changes materially, revise it and request approval again.

## 2. Implementation

Implement the approved plan. Run relevant tests and checks; inspect the diff,
affected contracts, execution modes, data effects, and migrations. Fix findings.
Present changed files, verification results, and remaining risks. **Wait for
explicit user acceptance before completion.** Then update only relevant
documentation, sync specs and archive the OpenSpec change when one exists.
**Before reporting completion, create one or more Git commits containing all
changes belonging to the accepted task, including its tests, documentation,
and OpenSpec artifacts.** Inspect the staged diff and keep unrelated existing
changes out of these commits. Verify the commits were created and report their
hashes in the final response. If committing fails, report the blocker instead
of claiming completion. Do not push or merge without separate permission.

For work spanning sessions, keep a short record in
`docs/workflow-runs/<task-slug>.md` with the plan, approval, current state,
checks, and next action. Read an existing record before resuming. A recorded
approval does not replace either review gate for a new or materially revised
plan or implementation.
